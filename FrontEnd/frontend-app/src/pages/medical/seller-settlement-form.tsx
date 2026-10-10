import {useEffect,useRef,useState} from 'react';
import {CheckCircle2,FileUp,LoaderCircle,Send} from 'lucide-react';
import api from '@/lib/api';
import {apiErrorMessage} from '@/lib/api-error';
import {Dialog,DialogContent,DialogHeader,DialogTitle,DialogDescription} from '@/components/side-dialog';
import {Button} from '@/components/ui/button';
import {Input} from '@/components/ui/input';
import {Textarea} from '@/components/ui/textarea';
import {SearchableSelect} from '@/components/searchable-select';
import {readVoucher,voucherFields} from './voucher-ocr';
type Entry={id:number;code:string;customer:string;deposit:string};
const money=(value:number)=>new Intl.NumberFormat('es-PE',{style:'currency',currency:'PEN'}).format(value);
export function SellerSettlementForm({profiles,close,saved}:{profiles:{value:string;label:string}[];close:()=>void;saved:()=>Promise<void>}){
 const [responsible,setResponsible]=useState(profiles.length===1?profiles[0].value:''),[rows,setRows]=useState<Entry[]>([]),[selected,setSelected]=useState<number[]>([]);
 const [loading,setLoading]=useState(false),[busy,setBusy]=useState(false),[reading,setReading]=useState(false),[error,setError]=useState(''),[ocrStatus,setOcrStatus]=useState('');
 const [file,setFile]=useState<File|null>(null),[text,setText]=useState(''),[note,setNote]=useState(''),[confirmed,setConfirmed]=useState(false),[done,setDone]=useState('');
 const [voucher,setVoucher]=useState({amount:'',reference:'',paid_on:'',bank:'',account:''});
 const generation=useRef(0);
 useEffect(()=>()=>{generation.current++;},[]);
 useEffect(()=>{
  setRows([]);setSelected([]);setConfirmed(false);if(!responsible)return;
  const abort=new AbortController();setLoading(true);setError('');
  api.get('/medical/seller-pending',{params:{responsible_id:responsible},signal:abort.signal}).then(r=>setRows(r.data.items)).catch(e=>{if(!abort.signal.aborted)setError(apiErrorMessage(e,'No se pudieron cargar los pendientes'));}).finally(()=>{if(!abort.signal.aborted)setLoading(false);});
  return()=>abort.abort();
 },[responsible]);
 const cents=rows.filter(i=>selected.includes(i.id)).reduce((n,i)=>n+Math.round(Number(i.deposit)*100),0);
 const matches=cents>0&&Math.round(Number(voucher.amount)*100)===cents;
 async function upload(next:File|undefined){
  if(!next)return;const version=++generation.current;setFile(next);setText('');setConfirmed(false);setVoucher({amount:'',reference:'',paid_on:'',bank:'',account:''});setReading(true);setOcrStatus('Leyendo voucher…');setError('');
  try{const value=await readVoucher(next,message=>{if(version===generation.current)setOcrStatus(message);});if(version!==generation.current)return;setText(value);setVoucher(voucherFields(value));setOcrStatus('Lectura completada. Revisa los datos detectados.');}
  catch(e){if(version===generation.current)setOcrStatus((e instanceof Error?e.message:'No se pudo leer el voucher')+' Completa y confirma los datos manualmente.');}
  finally{if(version===generation.current)setReading(false);}
 }
 async function submit(event:React.FormEvent){
  event.preventDefault();if(!file||!matches||!confirmed)return;setBusy(true);setError('');
  const body=new FormData();body.set('responsible_id',responsible);body.set('issuance_ids',JSON.stringify(selected));body.set('file',file);body.set('note',note);body.set('ocr_text',text);
  for(const [key,value]of Object.entries(voucher))body.set(key,value);
  try{const {data}=await api.post('/medical/seller-settlements',body);setDone(data.notification_status==='sent'?'Liquidación enviada a Oficina Principal. Correo enviado con el voucher.':data.notification_status==='uncertain'?'Liquidación enviada a Oficina Principal. La recepción del correo está por confirmar; no vuelvas a registrar la liquidación.':'Liquidación enviada a Oficina Principal. Correo en cola.');}
  catch(e){setError(apiErrorMessage(e,'No se pudo enviar la liquidación'));}finally{setBusy(false);}
 }
 return <Dialog open onOpenChange={v=>{if(!v&&!busy&&!reading){if(done)void saved();else close();}}}><DialogContent className="sm:max-w-4xl"><DialogHeader><DialogTitle>Enviar liquidación</DialogTitle><DialogDescription>Selecciona pendientes, adjunta el voucher y envía a Oficina Principal para su revisión.</DialogDescription></DialogHeader>
 {done?<div className="space-y-5 rounded-xl border border-emerald-200 bg-emerald-50 p-6 text-emerald-950"><CheckCircle2/><p>{done}</p><p>Estado: Enviado. Oficina Principal verificará el depósito y lo marcará Liquidado.</p><Button onClick={()=>void saved()}>Terminar</Button></div>:<form onSubmit={submit}><fieldset disabled={busy||reading} className="space-y-6">
 <label className="block space-y-2 text-sm">Responsable<SearchableSelect aria-label="Responsable de liquidación" value={responsible} onValueChange={setResponsible} options={profiles}/></label>
 <div className="max-h-64 overflow-auto rounded-xl border"><table className="w-full text-left text-sm"><thead className="bg-muted/40"><tr><th className="p-3"><input type="checkbox" aria-label="Seleccionar todos los pendientes" checked={!!rows.length&&selected.length===rows.length} onChange={e=>{setSelected(e.target.checked?rows.map(i=>i.id):[]);setConfirmed(false);}}/></th><th>Emisión y titular</th><th className="p-3 text-right">A depositar</th></tr></thead><tbody>{rows.map(i=><tr key={i.id} className="border-t"><td className="p-3"><input type="checkbox" aria-label={`Incluir ${i.code}`} checked={selected.includes(i.id)} onChange={e=>{setSelected(e.target.checked?[...selected,i.id]:selected.filter(id=>id!==i.id));setConfirmed(false);}}/></td><td className="py-3"><strong>{i.code}</strong><div className="text-muted-foreground">{i.customer}</div></td><td className="p-3 text-right">{money(Number(i.deposit))}</td></tr>)}{!rows.length&&<tr><td colSpan={3} className="p-6 text-center text-muted-foreground">{loading?'Cargando pendientes…':responsible?'No hay emisiones cobradas pendientes de liquidar.':'Selecciona un responsable.'}</td></tr>}</tbody></table></div>
 <div className="flex items-center justify-between rounded-xl bg-emerald-500/5 p-4"><span>{selected.length} emisiones seleccionadas</span><strong className="text-xl">{money(cents/100)}</strong></div>
 {!!selected.length&&<section className="space-y-4"><label className="block space-y-2 text-sm"><span className="flex items-center gap-2 font-semibold"><FileUp className="size-4"/>Voucher de depósito</span><Input aria-label="Voucher de depósito" type="file" accept="application/pdf,image/png,image/jpeg" required onChange={e=>void upload(e.target.files?.[0])}/></label><p role="status" className="text-sm text-muted-foreground">{reading&&<LoaderCircle className="mr-2 inline size-4 animate-spin"/>}{ocrStatus}</p>
 {file&&<><div className="grid gap-4 sm:grid-cols-2">{([['amount','Monto del voucher','number'],['reference','Número de operación','text'],['paid_on','Fecha de depósito','date'],['bank','Banco','text'],['account','Cuenta de destino (opcional)','text']] as const).map(([key,label,type])=><label key={key} className="space-y-1 text-sm">{label}<Input aria-label={label} type={type} required={key!=='account'} step={key==='amount'?'0.01':undefined} min={key==='amount'?'0.01':undefined} minLength={key==='reference'?3:undefined} maxLength={key==='account'?34:key==='bank'?80:key==='reference'?100:undefined} value={voucher[key]} onChange={e=>{setVoucher({...voucher,[key]:e.target.value});setConfirmed(false);}}/></label>)}</div>
 <p role="status" className={`rounded-lg p-3 text-sm ${matches?'bg-emerald-50 text-emerald-800':'bg-amber-50 text-amber-900'}`}>{matches?'El monto del voucher coincide con las emisiones seleccionadas.':`El voucher debe sumar ${money(cents/100)}. Revisa el monto y la selección.`}</p>
 <label className="block space-y-2 text-sm">Comentarios para Oficina Principal<Textarea value={note} onChange={e=>setNote(e.target.value)} maxLength={1000} placeholder="Comentario opcional"/></label>
 <label className="flex gap-2 text-sm"><input type="checkbox" checked={confirmed} onChange={e=>setConfirmed(e.target.checked)}/>Revisé las emisiones, el monto y los datos del voucher. Enviar a Oficina Principal.</label></>}
 </section>}{error&&<p role="alert" className="text-sm text-red-700">{error}</p>}
 <div className="flex justify-end gap-3 border-t pt-5"><Button type="button" variant="outline" onClick={close}>Cancelar</Button><Button type="submit" disabled={!matches||!file||!confirmed||loading}><Send className="size-4"/>{busy?'Enviando…':'Enviar a Oficina Principal'}</Button></div>
 </fieldset></form>}</DialogContent></Dialog>;
}
