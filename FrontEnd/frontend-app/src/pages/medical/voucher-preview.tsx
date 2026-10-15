import {useEffect,useState} from 'react';
import api from '@/lib/api';
import {apiErrorMessage} from '@/lib/api-error';
import {Button} from '@/components/ui/button';
import {Dialog,DialogContent,DialogHeader,DialogTitle,DialogDescription} from '@/components/side-dialog';
import type {SettlementDetail} from './liquidation-detail';

export function VoucherPreview({detail,close}:{detail:SettlementDetail;close:()=>void}) {
 const [selected,setSelected]=useState(detail.vouchers[0]?.id);
 const [preview,setPreview]=useState<{url:string;pdf:boolean}|null>(null);
 const [error,setError]=useState('');
 const [loading,setLoading]=useState(false);
 const voucher=detail.vouchers.find(v=>v.id===selected);
 useEffect(()=>{
  let cancelled=false;let url:string|undefined;
  setPreview(null);setError('');
  if(!voucher)return;
  setLoading(true);
  void api.get(`/medical/vouchers/${voucher.id}/file`,{responseType:'blob'}).then(({data})=>{
   if(cancelled)return;
   const pdf=/\.pdf$/i.test(voucher.filename);
   url=URL.createObjectURL(new Blob([data],{type:pdf?'application/pdf':/\.png$/i.test(voucher.filename)?'image/png':'image/jpeg'}));
   setPreview({url,pdf});
  }).catch(e=>{if(!cancelled)setError(apiErrorMessage(e,'No se pudo abrir el voucher'));}).finally(()=>{if(!cancelled)setLoading(false);});
  return ()=>{cancelled=true;if(url)URL.revokeObjectURL(url);};
 },[voucher]);
 return <Dialog open onOpenChange={open=>{if(!open)close();}}><DialogContent className="sm:max-w-4xl"><DialogHeader><DialogTitle>{detail.code} · Voucher</DialogTitle><DialogDescription>{detail.items.map(i=>i.customer).join(' · ')||'Sustento de la liquidación'}</DialogDescription></DialogHeader>
 {detail.vouchers.length>1&&<div className="flex flex-wrap gap-2">{detail.vouchers.map((v,index)=><Button key={v.id} size="sm" variant={selected===v.id?'default':'outline'} onClick={()=>setSelected(v.id)}>Voucher {index+1}</Button>)}</div>}
 {voucher&&<p className="text-sm">{voucher.paid_on} · S/ {Number(voucher.amount).toFixed(2)} · Operación {voucher.reference}</p>}
 {loading&&<p role="status">Cargando voucher…</p>}{error&&<p role="alert" className="text-red-700">{error}</p>}
 {!detail.vouchers.length&&<p className="text-sm text-muted-foreground">Sin voucher registrado.</p>}
 {preview&&(preview.pdf?<iframe title="Voucher" src={preview.url} className="h-[70vh] w-full rounded-lg border"/>:<img alt={voucher?.filename||'Voucher'} src={preview.url} className="mx-auto max-h-[70vh] max-w-full object-contain"/>)}
 </DialogContent></Dialog>;
}
