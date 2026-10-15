import {useState} from 'react';
import {CheckCircle2,FileText} from 'lucide-react';
import api from '@/lib/api';
import {apiErrorMessage} from '@/lib/api-error';
import {Button} from '@/components/ui/button';
import {Textarea} from '@/components/ui/textarea';
import {Dialog,DialogContent,DialogHeader,DialogTitle,DialogDescription} from '@/components/side-dialog';
import type {SettlementDetail} from './liquidation-detail';
import {VoucherPreview} from './voucher-preview';
export function SellerSettlementDetail({initial,close,changed,manager}:{initial:SettlementDetail;close:()=>void;changed:()=>Promise<void>;manager:boolean}){
 const [detail,setDetail]=useState(initial),[busy,setBusy]=useState(false),[error,setError]=useState(''),[reason,setReason]=useState('');
 const money=(s:string)=>new Intl.NumberFormat('es-PE',{style:'currency',currency:'PEN'}).format(Number(s));
 const [preview,setPreview]=useState<SettlementDetail|null>(null);
 async function finish(){setBusy(true);setError('');try{await api.post(`/medical/liquidations/${detail.id}/settle`,{reason});setDetail((await api.get(`/medical/liquidations/${detail.id}`)).data);await changed();}catch(e){setError(apiErrorMessage(e,'No se pudo confirmar la liquidación'));}finally{setBusy(false);}}
 return <><Dialog open onOpenChange={v=>{if(!v&&!busy)close();}}><DialogContent className="sm:max-w-3xl"><DialogHeader><DialogTitle>{detail.code}</DialogTitle><DialogDescription>{detail.status==='paid'?'Liquidado: depósito verificado por Oficina Principal.':'Enviado: pendiente de revisión por Oficina Principal.'}</DialogDescription></DialogHeader>
 <div className="rounded-xl bg-emerald-500/5 p-5"><p className="text-sm">{detail.items.length} emisiones incluidas</p><strong className="text-2xl">{money(detail.deposit_required)}</strong></div>
 {detail.office_notification&&<p className="text-sm text-muted-foreground">Correo a Oficina Principal: {detail.office_notification==='simulated'?'simulado (liquidacion de prueba)':detail.office_notification==='sent'?'enviado':detail.office_notification==='queued'?'en cola':detail.office_notification==='sending'?'en curso':'recepción por confirmar; revisar antes de repetir'}.</p>}
 <section className="space-y-3"><h3 className="font-semibold">Voucher y comentarios</h3>{detail.vouchers.map(v=><div key={v.id} className="rounded-xl border p-4 text-sm"><strong>{money(v.amount)}</strong><p>{v.bank} · Operación {v.reference} · {v.paid_on}</p><Button className="mt-3" variant="outline" onClick={()=>setPreview({...detail,vouchers:[v]})}><FileText className="size-4"/>Ver voucher</Button></div>)}{detail.notes&&<p className="whitespace-pre-wrap rounded-lg bg-muted/40 p-3 text-sm">{detail.notes}</p>}</section>
 <div className="max-h-64 overflow-auto rounded-xl border">{detail.items.map(i=><div key={i.id} className="flex justify-between gap-4 border-b p-3 text-sm"><span>{i.code} · {i.customer}{i.sale_date && <small className="block text-muted-foreground">Emisión: {i.sale_date.split("-").reverse().join("/")}</small>}</span><strong className="shrink-0">{money(i.deposit)}</strong></div>)}</div>
 {manager&&detail.status!=='paid'&&<section className="space-y-3 border-t pt-4"><p className="text-sm">Verifica la operación contra el banco antes de confirmar.</p><Textarea aria-label="Comentario de Oficina Principal" placeholder="Comentario de verificación" value={reason} onChange={e=>setReason(e.target.value)} minLength={5} maxLength={1000}/><Button disabled={busy||reason.trim().length<5} onClick={()=>void finish()}><CheckCircle2 className="size-4"/>{busy?'Confirmando…':'Aprobar y marcar Liquidado'}</Button></section>}{error&&<p role="alert" className="text-red-700">{error}</p>}
 </DialogContent></Dialog>{preview&&<VoucherPreview detail={preview} close={()=>setPreview(null)}/>}</>;
}
