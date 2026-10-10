import { useState } from 'react';
import axios from 'axios';
import api from '@/lib/api';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from '@/components/ui/dialog';

type Emission = { id:number; code:string; email?:string; phone?:string; token:string; test_batch?:string|null };
export function EmissionDelivery({row,close}:{row:Emission;close:()=>void}) {
  const [email,setEmail]=useState(row.email||'');
  const [phone,setPhone]=useState(row.phone||'');
  const [byEmail,setByEmail]=useState(true);
  const [byWhatsapp,setByWhatsapp]=useState(false);
  const [force,setForce]=useState(false);
  const [realTest,setRealTest]=useState(true);
  const [busy,setBusy]=useState(false);
  const [message,setMessage]=useState('');
  const official='https://abissol.org/?consulta='+btoa(JSON.stringify({code:row.token})).replace(/\+/g,'-').replace(/\//g,'_').replace(/=+$/,'');
  async function send(){
    setBusy(true);setMessage('');
    try{
      const {data}=await api.post(`/medical/emissions/${row.id}/send-client`,{email:byEmail,whatsapp:byWhatsapp,
        ...(byEmail?{recipient_email:email}:{}),...(byWhatsapp?{recipient_phone:phone}:{}),force,real_test:!!row.test_batch&&realTest});
      setMessage(data.data.map((r:{channel:string;status:string})=>`${r.channel==='email'?'Correo':'WhatsApp'}: ${r.status==='sent'?'aceptado por el proveedor':r.status==='simulated'?'simulado, sin envío real':'sin confirmación; revisa antes de reenviar'}`).join(' · '));
    }catch(e){const detail=axios.isAxiosError(e)?e.response?.data?.detail:null;setMessage(typeof detail==='string'?detail:'No se pudo enviar. Revisa los destinatarios y el historial.');}
    finally{setBusy(false);}
  }
  return <Dialog open onOpenChange={open=>{if(!open&&!busy)close();}}><DialogContent className="max-h-[90vh] overflow-y-auto"><DialogHeader><DialogTitle>Enviar confirmación · {row.code}</DialogTitle><DialogDescription>Correo con carta de bienvenida y condicionado; WhatsApp con el enlace de consulta en abissol.org.</DialogDescription></DialogHeader>
    <a className="text-sm text-emerald-700 underline" href={official} target="_blank" rel="noopener noreferrer">Verificar en la web oficial</a>
    {row.test_batch&&<div className="rounded-lg border border-amber-300 bg-amber-50 p-3 text-sm text-amber-950">PRUEBA: no acredita cobertura real ni envía a SUNAT. La recepción real solo se permite a los destinatarios autorizados.<label className="mt-2 flex gap-2"><input type="checkbox" checked={realTest} onChange={e=>setRealTest(e.target.checked)} disabled={busy}/>Enviar realmente a destinatarios de prueba autorizados</label></div>}
    <label className="flex gap-2"><input type="checkbox" checked={byEmail} onChange={e=>setByEmail(e.target.checked)} disabled={busy}/>Enviar por correo</label>
    {byEmail&&<Input type="email" aria-label="Correo del destinatario" value={email} onChange={e=>setEmail(e.target.value)} disabled={busy}/>}
    <label className="flex gap-2"><input type="checkbox" checked={byWhatsapp} onChange={e=>setByWhatsapp(e.target.checked)} disabled={busy}/>Enviar por WhatsApp</label>
    {byWhatsapp&&<Input type="tel" aria-label="WhatsApp del destinatario" placeholder="51999888777" value={phone} onChange={e=>setPhone(e.target.value)} disabled={busy}/>}
    <label className="flex gap-2 text-sm"><input type="checkbox" checked={force} onChange={e=>setForce(e.target.checked)} disabled={busy}/>Autorizar reenvío después de revisar los intentos anteriores</label>
    {message&&<p role="status" className="rounded-lg border p-3 text-sm">{message}</p>}
    <div className="flex justify-end gap-2"><Button variant="outline" onClick={close} disabled={busy}>Cerrar</Button><Button onClick={()=>void send()} disabled={busy||(!byEmail&&!byWhatsapp)||(byEmail&&!email)||(byWhatsapp&&!phone)}>{busy?'Enviando…':'Enviar confirmación'}</Button></div>
  </DialogContent></Dialog>;
}
