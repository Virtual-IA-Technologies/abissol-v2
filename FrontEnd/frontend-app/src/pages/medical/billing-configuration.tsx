import { useEffect, useState, type FormEvent } from 'react';
import axios from 'axios';
import api from '@/lib/api';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { SearchableSelect } from '@/components/searchable-select';

type Form = { enabled: boolean; environment: string; v2_series: string; company_name: string; trade_name: string; ruc: string; address: string; ubigeo: string; department: string; province: string; district: string; sol_user: string; sol_password: string; certificate_password: string };
type Configuration = Form & { imported: boolean; ready: boolean; problem: string; certificate_expires_at: string | null; v2_counter: number; credentials_preserved: boolean; certificate_preserved: boolean; series: {series:string;current_number:number}[]; distribution: Record<string,{description:string;total:string}[]> };
const fields = [['company_name','Razón social'],['trade_name','Nombre comercial'],['ruc','RUC'],['address','Dirección fiscal'],['ubigeo','Ubigeo'],['department','Departamento'],['province','Provincia'],['district','Distrito']] as const;
function formData(data: Configuration): Form {
  return { enabled:data.enabled, environment:data.environment || 'beta', v2_series:data.v2_series || '', company_name:data.company_name || '',trade_name:data.trade_name || '',ruc:data.ruc || '',address:data.address || '',ubigeo:data.ubigeo || '',department:data.department || '',province:data.province || '',district:data.district || '',sol_user:'',sol_password:'',certificate_password:'' };
}

export function BillingConfiguration({ updated }: { updated: () => Promise<void> }) {
  const [data,setData] = useState<Configuration | null>(null);
  const [form,setForm] = useState<Form | null>(null);
  const [message,setMessage] = useState('');
  const [busy,setBusy] = useState(false);
  useEffect(() => {
    const controller = new AbortController();
    api.get<Configuration>('/medical/billing/configuration',{signal:controller.signal}).then(r => {setData(r.data);setForm(formData(r.data));}).catch(() => {if(!controller.signal.aborted)setMessage('No se pudo consultar la configuración fiscal.');});
    return () => controller.abort();
  },[]);
  async function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();setBusy(true);setMessage('');
    try {
      const {data:next} = await api.put<Configuration>('/medical/billing/configuration',form);
      setData(next);setForm(formData(next));setMessage('Configuración guardada.');await updated();
    } catch(e) {const detail=axios.isAxiosError(e)?e.response?.data?.detail:null;setMessage(typeof detail==='string'?detail:'No se pudo guardar. Revisa los datos ingresados.');}
    finally {setBusy(false);}
  }
  if(!form || !data) return <p role="status">{message || 'Cargando configuración…'}</p>;
  if(!data.imported) return <p>No existe configuración fiscal importada.</p>;
  return <form onSubmit={save} className="space-y-5">
    <div className="rounded-xl border bg-emerald-500/5 p-5"><h2 className="text-lg font-semibold">Configuración fiscal · Programador</h2><p className="mt-1 text-sm text-muted-foreground">Boleta automática al registrar una nueva emisión; el cobro conserva su propio estado. Numeración y envío independientes del sistema anterior.</p></div>
    {message && <p role="status" className="rounded-lg border p-3 text-sm">{message}</p>}
    <fieldset disabled={busy} className="space-y-5">
      <section className="rounded-xl border p-5"><h3 className="mb-4 font-semibold">Emisor y domicilio fiscal</h3><div className="grid gap-4 md:grid-cols-2">{fields.map(([key,label]) => <label key={key} className="space-y-1 text-sm">{label}<Input aria-label={label} value={form[key]} required={key!=='trade_name'} maxLength={key==='ruc'?11:key==='ubigeo'?6:250} onChange={e=>setForm({...form,[key]:e.target.value})} /></label>)}</div></section>
      <section className="rounded-xl border p-5"><h3 className="mb-4 font-semibold">Automatización y numeración</h3><div className="grid gap-4 md:grid-cols-2"><label className="space-y-1 text-sm">Entorno<SearchableSelect aria-label="Entorno SUNAT" options={[{value:'beta',label:'Beta · pruebas sin validez fiscal'},{value:'production',label:'Producción · comprobantes reales'}]} value={form.environment} onValueChange={environment=>setForm({...form,environment})} disabled={busy} /></label><label className="space-y-1 text-sm">Serie exclusiva V2<Input aria-label="Serie exclusiva V2" placeholder="B…" value={form.v2_series} pattern="B[A-Z0-9]{3}" maxLength={4} required onChange={e=>setForm({...form,v2_series:e.target.value.toUpperCase()})} /></label></div><p className="mt-3 text-sm">Último correlativo V2: <strong>{data.v2_counter}</strong>. La numeración se asigna automáticamente y no se puede retroceder.</p><p className="mt-2 text-xs text-muted-foreground">Series conservadas del sistema anterior: {data.series.map(s=>`${s.series} (${s.current_number})`).join(' · ')}. No se reutilizan mientras el sistema anterior siga emitiendo.</p><label className="mt-4 flex items-center gap-2 text-sm"><input type="checkbox" checked={form.enabled} onChange={e=>setForm({...form,enabled:e.target.checked})} />Activar generación y envío automático de boletas a SUNAT</label></section>
      <section className="rounded-xl border p-5"><h3 className="mb-2 font-semibold">Credenciales y certificado</h3><p className="mb-4 text-sm text-muted-foreground">Credenciales {data.credentials_preserved?'conservadas':'pendientes'} · Certificado {data.certificate_preserved?'conservado':'pendiente'}{data.certificate_expires_at?` · Vence ${data.certificate_expires_at.slice(0,10)}`:''}. Deja las claves vacías para conservarlas.</p><div className="grid gap-4 md:grid-cols-3">{([['sol_user','Usuario SOL'],['sol_password','Clave SOL'],['certificate_password','Clave del certificado']] as const).map(([key,label])=><label key={key} className="space-y-1 text-sm">{label}<Input aria-label={label} type="password" autoComplete="new-password" value={form[key]} onChange={e=>setForm({...form,[key]:e.target.value})} /></label>)}</div><p className="mt-3 text-sm">{data.ready?'Configuración local completa. La aceptación de cada boleta se confirma con su CDR.':data.problem}</p></section>
      <section className="rounded-xl border p-5"><h3 className="mb-3 font-semibold">Distribución fiscal del modelo ABISSOL</h3><div className="grid gap-4 md:grid-cols-2">{Object.entries(data.distribution || {}).map(([name,items])=><div key={name} className="rounded-lg bg-muted/40 p-4"><h4 className="mb-2 font-medium">{name}</h4>{items.map(item=><p key={item.description} className="flex justify-between gap-3 py-1 text-sm"><span>{item.description}</span><strong className="whitespace-nowrap">S/ {item.total}</strong></p>)}<p className="mt-3 text-xs text-muted-foreground">Operación inafecta · afectación 30 · IGV S/ 0.00</p></div>)}</div></section>
      <Button type="submit" disabled={busy} className="bg-emerald-700 text-white hover:bg-emerald-800">{busy?'Guardando…':'Guardar configuración'}</Button>
    </fieldset>
  </form>;
}
