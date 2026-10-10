import {useEffect,useRef,useState} from 'react';
import {CheckCircle2,FileUp,LoaderCircle,Send} from 'lucide-react';
import api from '@/lib/api';
import {apiErrorMessage} from '@/lib/api-error';
import {Dialog,DialogContent,DialogHeader,DialogTitle,DialogDescription} from '@/components/side-dialog';
import {Button} from '@/components/ui/button';
import {Input} from '@/components/ui/input';
import {Textarea} from '@/components/ui/textarea';
import {SearchableSelect} from '@/components/searchable-select';
import {readVoucher,voucherFields,optimizeVoucher} from './voucher-ocr';
type Entry={id:number;code:string;customer:string;document_number?:string;deposit:string;responsible_id:number;eligible:boolean;test_batch?:string;payment_status:string};
const money=(value:number)=>new Intl.NumberFormat('es-PE',{style:'currency',currency:'PEN'}).format(value);
export function SellerSettlementForm({profiles,close,saved,inline=false}:{inline?:boolean;profiles:{value:string;label:string}[];close:()=>void;saved:()=>Promise<void>}){
 const [filter,setFilter]=useState('');
 const [responsible,setResponsible]=useState(''),[rows,setRows]=useState<Entry[]>([]),[selected,setSelected]=useState<number[]>([]);
 const [loading,setLoading]=useState(false),[busy,setBusy]=useState(false),[reading,setReading]=useState(false),[error,setError]=useState(''),[ocrStatus,setOcrStatus]=useState('');
 const [file,setFile]=useState<File|null>(null),[text,setText]=useState(''),[note,setNote]=useState(''),[confirmed,setConfirmed]=useState(false),[done,setDone]=useState('');
 const [voucher,setVoucher]=useState({amount:'',reference:'',paid_on:'',bank:'',account:''});
 const [attach,setAttach]=useState(false),[refresh,setRefresh]=useState(0);
 const generation=useRef(0);
 const [preview,setPreview]=useState('');
 useEffect(()=>{if(!file){setPreview('');return;}const url=URL.createObjectURL(file);setPreview(url);return()=>URL.revokeObjectURL(url);},[file]);
 useEffect(()=>()=>{generation.current++;},[]);
 useEffect(()=>{
  setRows([]);setSelected([]);setConfirmed(false);setAttach(false);setFile(null);
  const abort=new AbortController();setLoading(true);setError('');
  api.get('/medical/seller-pending',{params:responsible?{responsible_id:responsible}:{},signal:abort.signal}).then(r=>setRows(r.data.items)).catch(e=>{if(!abort.signal.aborted)setError(apiErrorMessage(e,'No se pudieron cargar los pendientes'));}).finally(()=>{if(!abort.signal.aborted)setLoading(false);});
  return()=>abort.abort();
 },[responsible,refresh]);
 const chosen=rows.find(i=>selected.includes(i.id));
 const owner=chosen?.responsible_id;
 const visibleRows=rows.filter(i=>`${i.code} ${i.customer} ${i.document_number||''}`.toLocaleLowerCase().includes(filter.toLocaleLowerCase()));
 const selectable=visibleRows.filter(i=>i.eligible&&(!owner||i.responsible_id===owner&&(i.test_batch||null)===(chosen?.test_batch||null)));
 async function finish(){setDone('');setFile(null);setSelected([]);setAttach(false);setRefresh(n=>n+1);await saved();}
 const cents=rows.filter(i=>selected.includes(i.id)).reduce((n,i)=>n+Math.round(Number(i.deposit)*100),0);
 const matches=cents>0&&Math.round(Number(voucher.amount)*100)===cents;
 async function upload(next:File|undefined){
  if(!next)return;const version=++generation.current;setFile(null);setText('');setConfirmed(false);setVoucher({amount:'',reference:'',paid_on:'',bank:'',account:''});setReading(true);setOcrStatus('Leyendo voucher…');setError('');
  try{const optimized=await optimizeVoucher(next);if(version!==generation.current)return;setFile(optimized);const value=await readVoucher(optimized,message=>{if(version===generation.current)setOcrStatus(message);});if(version!==generation.current)return;setText(value);setVoucher(voucherFields(value));setOcrStatus('Lectura completada. Revisa los datos detectados.');}
  catch(e){if(version===generation.current)setOcrStatus((e instanceof Error?e.message:'No se pudo leer el voucher')+' Completa y confirma los datos manualmente.');}
  finally{if(version===generation.current)setReading(false);}
 }
 async function submit(event:React.FormEvent){
  event.preventDefault();if(!file||!matches||!confirmed)return;setBusy(true);setError('');
  const body=new FormData();body.set('responsible_id',String(owner));body.set('issuance_ids',JSON.stringify(selected));body.set('file',file);body.set('note',note);body.set('ocr_text',text);
  for(const [key,value]of Object.entries(voucher))body.set(key,value);
  try{const {data}=await api.post('/medical/seller-settlements',body);setDone(data.notification_status==='simulated'?'Liquidaci\u00f3n de prueba registrada. Correo simulado; no afecta dep\u00f3sitos reales.':data.notification_status==='sent'?'Liquidación enviada a Oficina Principal. Correo enviado con el voucher.':data.notification_status==='uncertain'?'Liquidación enviada a Oficina Principal. La recepción del correo está por confirmar; no vuelvas a registrar la liquidación.':'Liquidación enviada a Oficina Principal. Correo en cola.');}
  catch(e){setError(apiErrorMessage(e,'No se pudo enviar la liquidación'));}finally{setBusy(false);}
 }
 const selection=<fieldset disabled={busy||reading} className="space-y-3"><div className="flex flex-wrap items-end gap-2"><label className="min-w-48 flex-1 text-xs text-muted-foreground">Buscar pendiente<Input className="h-9" aria-label="Buscar pendiente" placeholder="Certificado, titular o documento" value={filter} onChange={e=>setFilter(e.target.value)}/></label>{profiles.length>1&&<label className="w-64 text-xs text-muted-foreground">Responsable<SearchableSelect aria-label="Responsable de liquidación" value={responsible} onValueChange={setResponsible} options={[{value:"",label:"Todos"},...profiles]}/></label>}</div>
 <div className="max-h-64 overflow-auto rounded-xl border"><table className="w-full text-left text-sm"><thead className="bg-muted/40"><tr><th className="p-3"><input type="checkbox" aria-label="Seleccionar todos los pendientes" checked={!!selectable.length&&selectable.every(i=>selected.includes(i.id))} onChange={e=>{setSelected(e.target.checked?selectable.filter(i=>i.responsible_id===(owner||selectable[0]?.responsible_id)&&(i.test_batch||null)===((chosen||selectable[0])?.test_batch||null)).map(i=>i.id):[]);setConfirmed(false);}}/></th><th>Emisión y titular</th><th className="p-3 text-right">A depositar</th></tr></thead><tbody>{visibleRows.map(i=><tr key={i.id} className="border-t"><td className="p-3"><input type="checkbox" aria-label={`Incluir ${i.code}`} disabled={!i.eligible||!!owner&&(i.responsible_id!==owner||(i.test_batch||null)!==(chosen?.test_batch||null))} checked={selected.includes(i.id)} onChange={e=>{setSelected(e.target.checked?[...selected,i.id]:selected.filter(id=>id!==i.id));setConfirmed(false);}}/></td><td className="py-3"><strong>{i.code}</strong><div className="text-muted-foreground">{i.customer}</div><div className="text-xs text-muted-foreground">{profiles.find(p=>p.value===String(i.responsible_id))?.label} - {i.test_batch?"Prueba":"Pendiente de liquidar"}</div></td><td className="p-3 text-right">{money(Number(i.deposit))}</td></tr>)}{!visibleRows.length&&<tr><td colSpan={3} className="p-6 text-center text-muted-foreground">{loading?'Cargando pendientes…':'No hay emisiones pendientes.'}</td></tr>}</tbody></table></div>
 <div className="flex items-center justify-between rounded-xl bg-emerald-500/5 p-4"><span>{selected.length} emisiones seleccionadas</span><strong className="text-xl">{money(cents/100)}</strong></div>
 {!!selected.length&&!attach&&<Button type="button" onClick={()=>setAttach(true)}><FileUp className="size-4"/>Adjuntar voucher a {selected.length} emisiones</Button>}
</fieldset>;
 const content=<>
 {done?<div className="space-y-3 rounded-xl border border-emerald-200 bg-emerald-50 p-6 text-emerald-950"><CheckCircle2/><p>{done}</p><p>Estado: Enviado. Oficina Principal verificará el depósito y lo marcará Liquidado.</p><Button onClick={()=>void finish()}>Terminar</Button></div>:<form onSubmit={submit}><fieldset disabled={busy||reading} className="space-y-6">
 <div className="rounded-xl bg-emerald-500/5 p-4">{selected.length} emisiones seleccionadas - <strong>{money(cents/100)}</strong></div>
 {attach&&!!selected.length&&<section className="space-y-4"><label className="block space-y-2 text-sm"><span className="flex items-center gap-2 font-semibold"><FileUp className="size-4"/>Voucher de depósito</span><Input aria-label="Voucher de depósito" type="file" accept="application/pdf,image/png,image/jpeg" required onChange={e=>void upload(e.target.files?.[0])}/></label><p role="status" className="text-sm text-muted-foreground">{reading&&<LoaderCircle className="mr-2 inline size-4 animate-spin"/>}{ocrStatus}</p>
 {file&&<>{preview&&<div className="rounded-xl border bg-muted/20 p-3">{file.type==='application/pdf'?<iframe title="Vista previa del voucher" src={preview} className="h-96 w-full"/>:<img alt="Vista previa del voucher" src={preview} className="mx-auto max-h-96 max-w-full object-contain"/>}<p className="mt-2 text-xs text-muted-foreground">{file.name} - {Math.round(file.size/1024)} KB</p></div>}<div className="grid gap-4 sm:grid-cols-2">{([['amount','Monto del voucher','number'],['reference','Número de operación','text'],['paid_on','Fecha de depósito','date'],['bank','Banco','text'],['account','Cuenta de destino (opcional)','text']] as const).map(([key,label,type])=><label key={key} className="space-y-1 text-sm">{label}<Input aria-label={label} type={type} required={key!=='account'} step={key==='amount'?'0.01':undefined} min={key==='amount'?'0.01':undefined} minLength={key==='reference'?3:undefined} maxLength={key==='account'?34:key==='bank'?80:key==='reference'?100:undefined} value={voucher[key]} onChange={e=>{setVoucher({...voucher,[key]:e.target.value});setConfirmed(false);}}/></label>)}</div>
 <p role="status" className={`rounded-lg p-3 text-sm ${matches?'bg-emerald-50 text-emerald-800':'bg-amber-50 text-amber-900'}`}>{matches?'El monto del voucher coincide con las emisiones seleccionadas.':`El voucher debe sumar ${money(cents/100)}. Revisa el monto y la selección.`}</p>
 <label className="block space-y-2 text-sm">Comentarios para Oficina Principal<Textarea value={note} onChange={e=>setNote(e.target.value)} maxLength={1000} placeholder="Comentario opcional"/></label>
 <label className="flex gap-2 text-sm"><input type="checkbox" checked={confirmed} onChange={e=>setConfirmed(e.target.checked)}/>Revisé las emisiones, el monto y los datos del voucher. Enviar a Oficina Principal.</label></>}
 </section>}{error&&<p role="alert" className="text-sm text-red-700">{error}</p>}
 {attach&&<div className="flex justify-end gap-3 border-t pt-5"><Button type="button" variant="outline" onClick={()=>{setAttach(false);setFile(null);setConfirmed(false);}}>Cancelar</Button><Button type="submit" disabled={!matches||!file||!confirmed||loading}><Send className="size-4"/>{busy?'Enviando…':'Enviar a Oficina Principal'}</Button></div>}
 </fieldset></form>}</>;
 return inline?<section className="space-y-3 rounded-xl border bg-card p-3"><div><h2 className="text-lg font-semibold">Emisiones pendientes</h2></div>{selection}<Dialog open={attach||!!done} onOpenChange={v=>{if(!v&&!busy&&!reading){if(done)void finish();else setAttach(false);}}}><DialogContent className="sm:max-w-3xl"><DialogHeader><DialogTitle>Voucher y liquidación</DialogTitle><DialogDescription>Revisa el voucher y confirma el envío a Oficina Principal.</DialogDescription></DialogHeader>{content}</DialogContent></Dialog></section>:<Dialog open onOpenChange={v=>{if(!v&&!busy&&!reading)close();}}><DialogContent className="sm:max-w-4xl"><DialogHeader><DialogTitle>Enviar liquidación</DialogTitle><DialogDescription>Selecciona pendientes y adjunta el voucher.</DialogDescription></DialogHeader>{attach||done?content:selection}</DialogContent></Dialog>;
}
