import { useEffect, useRef, useState, type FormEvent } from 'react';
import axios from 'axios';
import { CalendarDays, CheckCircle2, HeartPulse, LoaderCircle, Search, ShieldCheck, UserRound, Wallet } from 'lucide-react';
import api from '@/lib/api';
import { Button } from '@/components/ui/button';
import { SearchableSelect } from '@/components/searchable-select';
import { Input } from '@/components/ui/input';
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from '@/components/side-dialog';

type Row = Record<string, string | number | boolean | null>;
type Option = { value: string; label: string };
type Identity = { full_name?: string; first_names?: string; paternal_surname?: string; maternal_surname?: string };
const selectClass = 'h-11 w-full rounded-lg border bg-background px-3 text-sm focus-visible:outline-emerald-600';
const money = (v: unknown) => new Intl.NumberFormat('es-PE', { style: 'currency', currency: 'PEN' }).format(Number(v || 0));

function tomorrowInLima(now = new Date()) {
  const parts = new Intl.DateTimeFormat('en-CA', { timeZone: 'America/Lima', year: 'numeric', month: '2-digit', day: '2-digit' }).formatToParts(now);
  const part = (key: string) => Number(parts.find(p => p.type === key)?.value);
  return new Date(Date.UTC(part('year'), part('month') - 1, part('day') + 1)).toISOString().slice(0, 10);
}
function dateLabel(value: string) {
  return value ? new Intl.DateTimeFormat('es-PE', { day: '2-digit', month: 'long', year: 'numeric', timeZone: 'UTC' }).format(new Date(value + 'T12:00:00Z')) : 'Selecciona una fecha';
}

export function EmissionForm({ plans, emitters, globalAccess, close, saved }: { plans: Row[]; emitters: Option[]; globalAccess: boolean; close: () => void; saved: () => Promise<void> }) {
  const [form, setForm] = useState(() => ({ plan_id: plans.length === 1 ? String(plans[0].id) : '', emitter_id: emitters.length === 1 ? emitters[0].value : '', document_type: 'DNI', document_number: '', customer: '', first_names: '', paternal_surname: '', maternal_surname: '', email: '', phone: '', starts_on: tomorrowInLima(), payment_method: 'cash', payment_status: 'pending' }));
  const [billing, setBilling] = useState({ invoice_type_code: '03', customer_document_type: 'RUC', customer_document_number: '', customer_name: '', customer_address: '', customer_ubigeo: '', due_date: '' });
  const [rucStatus, setRucStatus] = useState('');
  const billingRevision = useRef(0);
  useEffect(() => {
    if (billing.invoice_type_code !== '01' || !/^\d{11}$/.test(billing.customer_document_number)) return;
    const controller = new AbortController(); const version = billingRevision.current;
    const timer = setTimeout(async () => {
      setRucStatus('Consultando RUC…');
      try {
        const {data} = await api.post<{business_name?:string;address?:string;ubigeo?:string}>('/smart-forms/documents/lookup', {option_slug:'medical-emissions',document_type:'ruc',document_number:billing.customer_document_number}, {signal:controller.signal});
        if(controller.signal.aborted || version!==billingRevision.current)return;
        setBilling(current=>({...current,customer_name:data.business_name || current.customer_name,customer_address:data.address || current.customer_address,customer_ubigeo:data.ubigeo || current.customer_ubigeo}));
        setRucStatus('RUC consultado. Revisa los datos del adquirente.');
      } catch {if(!controller.signal.aborted)setRucStatus('No se pudo consultar el RUC. Completa los datos manualmente.');}
    },350);
    return ()=>{controller.abort();clearTimeout(timer);};
  },[billing.invoice_type_code,billing.customer_document_number]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [lookup, setLookup] = useState({ state: 'idle', message: '' });
  const revision = useRef(0);
  const nameRevision = useRef(0);
  const cache = useRef(new Map<string, Identity>());
  const minimum = tomorrowInLima();
  const plan = plans.find(p => String(p.id) === form.plan_id);
  const end = form.starts_on && plan ? new Date(Date.parse(form.starts_on + 'T12:00:00Z') + (Number(plan.validity_days) - 1) * 86400000).toISOString().slice(0, 10) : '';

  useEffect(() => {
    if (form.document_type !== 'DNI' || !/^\d{8}$/.test(form.document_number)) return;
    const controller = new AbortController();
    const generation = revision.current;
    const manualName = nameRevision.current;
    const dni = form.document_number;
    const timer = setTimeout(async () => {
      setLookup({ state: 'loading', message: 'Consultando DNI…' });
      try {
        let identity = cache.current.get(dni);
        if (!identity) {
          const { data } = await api.post<Identity>('/smart-forms/documents/lookup', { option_slug: 'medical-emissions', document_type: 'dni', document_number: dni }, { signal: controller.signal });
          if (!data.first_names && !data.full_name) throw new Error('empty');
          identity = data;
          cache.current.set(dni, data);
        }
        if (controller.signal.aborted || generation !== revision.current) return;
        if (manualName === nameRevision.current) {
          const names = { first_names: identity.first_names || identity.full_name || '', paternal_surname: identity.paternal_surname || '', maternal_surname: identity.maternal_surname || '' };
          setForm(current => ({ ...current, ...names, customer: Object.values(names).filter(Boolean).join(' ') }));
        }
        setLookup({ state: 'success', message: manualName === nameRevision.current ? 'DNI encontrado. Nombres y apellidos completados.' : 'DNI encontrado. Se conserva el nombre que editaste.' });
      } catch (e) {
        if (controller.signal.aborted || generation !== revision.current) return;
        setLookup({ state: 'error', message: axios.isAxiosError(e) && e.response?.status === 404 ? 'DNI no encontrado. Revisa el número o completa los nombres manualmente.' : 'No se pudo consultar el DNI. Puedes completar los nombres manualmente.' });
      }
    }, 350);
    return () => { controller.abort(); clearTimeout(timer); };
  }, [form.document_type, form.document_number]);

  function changeDocument(field: 'document_type' | 'document_number', value: string) {
    revision.current += 1;
    setLookup({ state: 'idle', message: '' });
    setForm(current => ({ ...current, [field]: value, ...(field === 'document_type' ? { document_number: '' } : {}), customer: '', first_names: '', paternal_surname: '', maternal_surname: '' }));
  }
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!form.plan_id || !form.emitter_id) { setError('Selecciona el plan y el emisor.'); return; }
    if (form.starts_on < tomorrowInLima()) { setError('La vigencia debe comenzar mañana o después, según la hora de Lima.'); return; }
    setBusy(true); setError('');
    try {
      await api.post('/medical/emissions', { ...form, customer: form.customer.trim(), plan_id: Number(form.plan_id), emitter_id: Number(form.emitter_id), billing: billing.invoice_type_code === '01' ? { ...billing, due_date: form.payment_status === 'pending' ? billing.due_date || null : null } : { invoice_type_code: '03' } });
      await saved();
    } catch (e) {
      const detail = axios.isAxiosError(e) ? e.response?.data?.detail : null;
      setError(typeof detail === 'string' ? detail : Array.isArray(detail) ? detail.map(i => i.msg).join(' · ') : 'No se pudo guardar la emisión. Revisa los datos e inténtalo nuevamente.');
    } finally { setBusy(false); }
  }
  return <Dialog open onOpenChange={open => { if (!open && !busy) close(); }}><DialogContent className="max-h-[94dvh] overflow-y-auto p-0 sm:max-w-4xl">
    <DialogHeader className="border-b bg-emerald-500/5 px-6 py-5 text-left"><div className="mb-2 flex items-center gap-2 text-xs font-semibold uppercase tracking-widest text-emerald-700 dark:text-emerald-400"><HeartPulse className="size-4" /> Programas de asistencia</div><DialogTitle className="text-2xl">Nueva emisión</DialogTitle><DialogDescription>Completa los datos del titular y elige cuándo empieza su protección.</DialogDescription></DialogHeader>
    <form onSubmit={submit} className="min-w-0"><fieldset disabled={busy} className="grid min-w-0 md:grid-cols-[1fr_250px]">
      <div className="min-w-0 space-y-6 p-6">
        {error && <p role="alert" className="rounded-lg bg-red-500/10 p-3 text-sm text-red-700">{error}</p>}
        <section className="space-y-3"><h3 className="flex items-center gap-2 font-semibold"><ShieldCheck className="size-4 text-emerald-600" /> Programa y emisor</h3><div className="grid gap-4 sm:grid-cols-2">
          <label className="space-y-1.5 text-sm">Plan de asistencia<SearchableSelect aria-label="Plan de asistencia" className={selectClass} disabled={busy} value={form.plan_id} onValueChange={value => setForm({ ...form, plan_id: value })} options={plans.map(p => ({ value: String(p.id), label: `${String(p.name)} · ${money(p.price)}` }))} placeholder="Seleccionar plan" /></label>
          <label className="space-y-1.5 text-sm">Emisor<SearchableSelect aria-label="Emisor" className={selectClass} disabled={busy} value={form.emitter_id} onValueChange={value => setForm({ ...form, emitter_id: value })} options={emitters} placeholder="Seleccionar emisor" /></label>
        </div></section>
        <section className="space-y-3 border-t pt-5"><h3 className="flex items-center gap-2 font-semibold"><UserRound className="size-4 text-emerald-600" /> Datos del titular</h3><div className="grid gap-4 sm:grid-cols-[140px_1fr]">
          <label className="space-y-1.5 text-sm">Documento<SearchableSelect aria-label="Tipo de documento" className={selectClass} disabled={busy} value={form.document_type} onValueChange={value => changeDocument('document_type', value)} options={[{value:'DNI',label:'DNI'},{value:'CE',label:'Carné de extranjería'},{value:'PASSPORT',label:'Pasaporte'}]} placeholder="Seleccionar documento" /></label>
          <label className="space-y-1.5 text-sm">Número de documento<div className="relative"><Input className="h-11 pr-10" aria-label="Número de documento" aria-describedby="dni-status" autoComplete="off" inputMode={form.document_type === 'DNI' ? 'numeric' : 'text'} maxLength={form.document_type === 'DNI' ? 8 : 20} minLength={form.document_type === 'DNI' ? 8 : 6} pattern={form.document_type === 'DNI' ? '[0-9]{8}' : '[A-Za-z0-9]{6,20}'} value={form.document_number} placeholder={form.document_type === 'DNI' ? 'Ingresa los 8 dígitos' : 'Número de documento'} onChange={e => changeDocument('document_number', form.document_type === 'DNI' ? e.target.value.replace(/\D/g, '').slice(0, 8) : e.target.value.replace(/[^A-Za-z0-9]/g, ''))} required />{lookup.state === 'loading' ? <LoaderCircle className="absolute right-3 top-3 size-5 animate-spin text-emerald-600" /> : lookup.state === 'success' ? <CheckCircle2 className="absolute right-3 top-3 size-5 text-emerald-600" /> : <Search className="absolute right-3 top-3 size-5 text-muted-foreground" />}</div></label>
        </div><p id="dni-status" role="status" aria-live="polite" className={`text-xs ${lookup.state === 'error' ? 'text-amber-700 dark:text-amber-400' : lookup.state === 'success' ? 'text-emerald-700 dark:text-emerald-400' : 'text-muted-foreground'}`}>{lookup.message || (form.document_type === 'DNI' ? 'Consulta automática al completar los 8 dígitos del DNI.' : 'Completa los datos del titular manualmente.')}</p>
          <div className="grid gap-4 sm:grid-cols-3">{([
            ['first_names', 'Nombres', 100], ['paternal_surname', 'Apellido paterno', 80], ['maternal_surname', 'Apellido materno', 80],
          ] as const).map(([field, label, max]) => <label key={field} className="space-y-1.5 text-sm">{label}<Input className="h-11" aria-label={label} maxLength={max} value={form[field]} required={field === 'first_names'} onChange={e => {
            nameRevision.current += 1;
            const next = { ...form, [field]: e.target.value };
            next.customer = [next.first_names, next.paternal_surname, next.maternal_surname].map(v => v.trim()).filter(Boolean).join(' ');
            setForm(next);
          }} /></label>)}</div>

          <div className="grid gap-4 sm:grid-cols-2"><label className="space-y-1.5 text-sm">Correo <span className="text-muted-foreground">(opcional)</span><Input className="h-11" aria-label="Correo" type="email" autoComplete="email" value={form.email} onChange={e => setForm({ ...form, email: e.target.value })} /></label><label className="space-y-1.5 text-sm">Celular <span className="text-muted-foreground">(opcional)</span><Input className="h-11" aria-label="Celular" type="tel" autoComplete="tel" maxLength={25} value={form.phone} onChange={e => setForm({ ...form, phone: e.target.value })} /></label></div>
        </section>
        <section className="space-y-3 border-t pt-5"><h3 className="font-semibold">Comprobante del programa</h3>
          <label className="block space-y-1.5 text-sm">Tipo de comprobante<SearchableSelect aria-label="Tipo de comprobante" disabled={busy} value={billing.invoice_type_code} options={[{value:'03',label:'Boleta · titular del programa'},{value:'01',label:'Factura · adquirente con RUC'}]} onValueChange={value=>setBilling({...billing,invoice_type_code:value})}/></label>
          {billing.invoice_type_code==='01'&&<><div className="grid gap-4 sm:grid-cols-2">{([['customer_document_number','RUC del adquirente',11],['customer_name','Razón social del adquirente',180],['customer_address','Dirección fiscal del adquirente',250],['customer_ubigeo','Ubigeo del adquirente',6]] as const).map(([key,label,max])=><label key={key} className="space-y-1.5 text-sm">{label}<Input aria-label={label} required value={billing[key]} maxLength={max} pattern={key==='customer_document_number'?'[0-9]{11}':key==='customer_ubigeo'?'[0-9]{6}':undefined} onChange={e=>{billingRevision.current+=1;setBilling({...billing,[key]:e.target.value,...(key==='customer_document_number'?{customer_name:'',customer_address:'',customer_ubigeo:''}:{})});}}/></label>)}</div><p role="status" className="text-xs text-muted-foreground">{rucStatus}</p>{form.payment_status==='pending'&&<label className="block space-y-1.5 text-sm">Vencimiento del pago a crédito<Input aria-label="Vencimiento del pago a crédito" type="date" required min={minimum} value={billing.due_date} onChange={e=>setBilling({...billing,due_date:e.target.value})}/></label>}<p className="text-xs text-muted-foreground">El titular conserva su cobertura personal; la factura identifica al adquirente con RUC. El tipo no se cambia después de numerar.</p></>}
        </section>
        <section className="space-y-3 border-t pt-5"><h3 className="flex items-center gap-2 font-semibold"><CalendarDays className="size-4 text-emerald-600" /> Vigencia y pago</h3><label className="block space-y-1.5 text-sm">Inicio de vigencia<Input className="h-11" aria-label="Inicio de vigencia" type="date" min={minimum} value={form.starts_on} onChange={e => setForm({ ...form, starts_on: e.target.value })} required /></label><p className="text-xs text-muted-foreground">Desde mañana o una fecha posterior. No se permite iniciar hoy ni en fechas anteriores. Hora de Lima.</p><div className="grid gap-4 sm:grid-cols-2">
          <label className="space-y-1.5 text-sm">Medio de pago<SearchableSelect aria-label="Medio de pago" className={selectClass} disabled={busy} value={form.payment_method} onValueChange={value => setForm({ ...form, payment_method: value, ...(value === 'online' && form.payment_status === 'collected_by_seller' ? { payment_status: 'pending' } : {}) })} options={[['cash','Efectivo'],['transfer','Transferencia'],['card','Tarjeta'],['online','En línea']].map(([value,label]) => ({value,label}))} placeholder="Seleccionar medio" /></label>
          <label className="space-y-1.5 text-sm">Estado del pago<SearchableSelect aria-label="Estado del pago" className={selectClass} disabled={busy} value={form.payment_status} onValueChange={value => setForm({ ...form, payment_status: value })} options={[{value:'pending',label:'Pendiente de cobro'},...(form.payment_method !== 'online' ? [{value:'collected_by_seller',label:'Cobrado por vendedor'}] : []),...(globalAccess ? [{value:'paid_to_abissol',label:'Ingresado a ABISSOL'}] : [])]} placeholder="Seleccionar estado" /></label>
        </div></section>
      </div>
      <aside className="min-w-0 space-y-5 border-t bg-muted/30 p-6 md:border-l md:border-t-0"><div className="flex items-center gap-2 text-sm font-semibold"><Wallet className="size-4 text-emerald-600" /> Resumen de emisión</div><div><p className="text-sm text-muted-foreground">Plan seleccionado</p><p className="mt-1 font-semibold">{String(plan?.name || 'Elige un plan')}</p><p className="mt-3 text-3xl font-semibold tracking-tight text-emerald-700 dark:text-emerald-400">{plan ? money(plan.price) : '—'}</p></div><div className="space-y-3 border-t pt-4 text-sm"><div><p className="text-muted-foreground">Inicio</p><p className="mt-1 font-medium">{dateLabel(form.starts_on)}</p></div><div><p className="text-muted-foreground">Fin de vigencia</p><p className="mt-1 font-medium">{end ? dateLabel(end) : 'Según el plan'}</p></div>{plan && <p className="text-muted-foreground">{String(plan.validity_days)} días de cobertura</p>}</div><p className="rounded-xl border border-emerald-500/20 bg-emerald-500/5 p-3 text-xs leading-relaxed text-muted-foreground">Revisa el documento, el titular y la vigencia antes de emitir. El precio vigente se confirma al guardar.</p></aside>
    </fieldset><footer className="flex items-center justify-end gap-3 border-t bg-background px-6 py-4"><Button type="button" variant="outline" onClick={close} disabled={busy}>Cancelar</Button><Button type="submit" className="bg-emerald-700 text-white hover:bg-emerald-800" disabled={busy || lookup.state === 'loading'}>{busy ? <LoaderCircle className="size-4 animate-spin" /> : <ShieldCheck className="size-4" />}{busy ? 'Guardando…' : 'Emitir programa'}</Button></footer></form>
  </DialogContent></Dialog>;
}
