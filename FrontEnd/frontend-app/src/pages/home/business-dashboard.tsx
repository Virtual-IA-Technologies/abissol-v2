import {useCallback, useEffect, useRef, useState} from 'react';
import {ArrowUpRight, CheckCheck, FileCheck2, HeartPulse, RefreshCw, Wallet} from 'lucide-react';
import {Link} from 'react-router-dom';
import {useAuth} from '@/context/AuthContext';
import {Button} from '@/components/ui/button';
import api from '@/lib/api';
import {apiErrorMessage} from '@/lib/api-error';
import './dashboard.css';

type Totals = {count:number;amount:string};
type Dashboard = {since:string;until:string;emissions:null|{count:number;sales:string;active:number;pending_count:number;pending_amount:string;trend:{date:string;count:number;sales:string}[];recent:{code:string;plan:string;date:string;amount:string}[]};liquidations:null|Record<'paid'|'review'|'preparing',Totals>};
const currency = new Intl.NumberFormat('es-PE',{style:'currency',currency:'PEN'});
const money = (v:string|number)=>currency.format(Number(v));
const shortDate=(date:string)=>new Date(date+'T12:00:00').toLocaleDateString('es-PE',{day:'2-digit',month:'short'});
const emissionsPath='/plataforma/medical/emissions';
const liquidationsPath='/plataforma/medical/liquidations';

export default function ControlPanel(){
 const {user,token,access}=useAuth();
 return <DashboardView key={`${user?.id}:${token}:${JSON.stringify(access)}`} name={user?.nombre||''}/>;
}
function DashboardView({name}:{name:string}){
 const {can}=useAuth();
 const [months,setMonths]=useState(3),[data,setData]=useState<Dashboard|null>(null),[busy,setBusy]=useState(true),[error,setError]=useState('');
 const pending=useRef<{months:number;request:Promise<Dashboard>}|null>(null);
 const sequence=useRef(0);
 const load=useCallback(async()=>{
  const version=++sequence.current;setBusy(true);setError('');
  if(pending.current?.months!==months){
   const request=api.get<Dashboard>('/medical/dashboard',{params:{months}}).then(r=>r.data).finally(()=>{if(pending.current?.request===request)pending.current=null;});
   pending.current={months,request};
  }
  try{const next=await pending.current.request;if(version===sequence.current)setData(next);}
  catch(e){if(version===sequence.current){setData(null);setError(apiErrorMessage(e,'No se pudo cargar el resumen'));}}
  finally{if(version===sequence.current)setBusy(false);}
 },[months]);
 useEffect(()=>{void load();return()=>{sequence.current++;};},[load]);
 const e=data?.emissions,l=data?.liquidations;
 const cards=[...(e?[
  {title:'Emisiones',value:String(e.count),note:'En el período',icon:FileCheck2,to:emissionsPath},
  {title:'Venta emitida',value:money(e.sales),note:'En el período',icon:Wallet,to:emissionsPath},
  {title:'Programas vigentes',value:String(e.active),note:'Al día de hoy',icon:HeartPulse,to:emissionsPath},
 ]:[]),...(e&&can('medical-liquidations')?[{title:'Por liquidar',value:money(e.pending_amount),note:`${e.pending_count} emisiones · todos los períodos`,icon:CheckCheck,to:liquidationsPath}]:[])];
 const byDate=new Map(e?.trend.map(p=>[p.date,p]));
 const trend=Array.from({length:months},(_,i)=>{const start=new Date(`${data?.since||'2000-01-01'}T12:00:00Z`);start.setUTCMonth(start.getUTCMonth()+i);const month=start.toISOString().slice(0,7)+'-01';return {date:month,...byDate.get(month),count:byDate.get(month)?.count||0};});
 const monthLabel=(date:string)=>new Date(date+'T12:00:00').toLocaleDateString('es-PE',{month:'short',year:'numeric'});
 const max=Math.max(1,...trend.map(p=>p.count));
 const total=l?Object.values(l).reduce((n,s)=>n+s.count,0):0;
 const states=[{key:'review' as const,label:'Por revisar',color:'#38bdf8'},{key:'paid' as const,label:'Liquidadas',color:'#10b981'},{key:'preparing' as const,label:'En preparación',color:'#fbbf24'}];
 return <main className="abissol-dashboard space-y-5 p-4 md:p-6" aria-busy={busy}>
  <header className="flex flex-wrap items-center justify-between gap-3"><div><p className="text-xs font-medium tracking-widest text-emerald-600">ABISSOL</p><h1 className="text-2xl font-semibold">Panel principal</h1><p className="mt-1 text-sm text-muted-foreground">Hola{name?`, ${name.split(' ')[0]}`:''}. Tu actividad, en un vistazo.</p></div><div className="flex flex-wrap items-center gap-2"><div className="flex rounded-xl border bg-card p-1" aria-label="Período de emisiones">{[1,3,6,12].map(value=><Button key={value} size="sm" variant={months===value?'secondary':'ghost'} aria-pressed={months===value} disabled={busy} onClick={()=>setMonths(value)}>{value} {value===1?'mes':'meses'}</Button>)}</div><Button size="sm" variant="outline" disabled={busy} onClick={()=>void load()}><RefreshCw className={`size-4 ${busy?'motion-safe:animate-spin':''}`}/>Actualizar</Button></div></header>
  {error&&<div role="alert" className="rounded-xl border border-red-300 p-4 text-sm text-red-700">{error}</div>}
  {!data&&busy&&<div role="status" className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">{[0,1,2,3].map(i=><div key={i} className="h-32 rounded-2xl bg-muted motion-safe:animate-pulse"/>)}<span className="sr-only">Cargando indicadores</span></div>}
  {data&&<>
   <section className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4" aria-label="Indicadores">{cards.map(({title,value,note,icon:Icon,to})=><Link key={title} to={to} className="dashboard-card rounded-2xl border bg-card p-5"><div className="flex items-center justify-between"><span className="text-xs text-muted-foreground">{title}</span><Icon className="size-5 text-emerald-600"/></div><p className="mt-3 text-3xl font-semibold tabular-nums tracking-tight">{value}</p><p className="mt-2 text-xs text-muted-foreground">{note}</p></Link>)}</section>
   <section className={`grid gap-4 ${e&&l?'xl:grid-cols-[1.5fr_1fr]':''}`}>
    {e&&<article className="min-w-0 rounded-2xl border bg-card p-5"><div className="flex items-start justify-between gap-3"><div><h2 className="text-sm font-semibold">Emisiones por mes</h2><p className="mt-1 text-xs text-muted-foreground">{monthLabel(data.since)} – {monthLabel(data.until.slice(0,7)+'-01')} · {e.count} emisiones</p></div><Link aria-label="Abrir emisiones" to={emissionsPath}><ArrowUpRight className="size-5 text-muted-foreground"/></Link></div><div className="mt-5 flex h-48 items-end gap-2" role="img" aria-label={`${e.count} emisiones en ${months} ${months===1?'mes':'meses'}`}>{trend.map(p=><div key={p.date} className="flex h-full min-w-0 flex-1 items-end" title={`${monthLabel(p.date)}: ${p.count} emisiones${p.sales?' · '+money(p.sales):''}`}><div className="dashboard-bar w-full rounded-t-sm bg-emerald-500/80" style={{height:p.count?`${p.count/max*100}%`:'2px',opacity:p.count?1:0.18}}/></div>)}</div><div className="mt-3 flex justify-between text-xs text-muted-foreground"><span>{monthLabel(data.since)}</span><span>Máximo mensual: {max===1&&!e.count?0:max}</span><span>{monthLabel(data.until.slice(0,7)+'-01')}</span></div>{!e.count&&<p className="mt-3 text-xs text-muted-foreground">Sin emisiones en este período.</p>}</article>}
    {l&&<article className="rounded-2xl border bg-card p-5"><div className="flex justify-between"><div><h2 className="text-sm font-semibold">Liquidaciones de vendedores</h2><p className="mt-1 text-xs text-muted-foreground">Todos los períodos</p></div><Link to={liquidationsPath} aria-label="Abrir liquidaciones"><ArrowUpRight className="size-5 text-muted-foreground"/></Link></div><div className="mt-5 flex flex-wrap items-center justify-center gap-6"><div className="relative size-40 shrink-0"><svg viewBox="0 0 120 120" className="size-full -rotate-90" role="img" aria-label={`${total} liquidaciones`}><circle cx="60" cy="60" r="48" fill="none" stroke="currentColor" className="text-muted" strokeWidth="11"/>{states.map((s,i)=>{const length=total?l[s.key].count/total*100:0;const start=total?states.slice(0,i).reduce((sum,x)=>sum+l[x.key].count,0)/total*100:0;return <circle key={s.key} cx="60" cy="60" r="48" fill="none" stroke={s.color} strokeWidth="11" pathLength="100" strokeDasharray={`${length} ${100-length}`} strokeDashoffset={-start} className="dashboard-ring"/>;})}</svg><div className="absolute inset-0 flex flex-col items-center justify-center"><strong className="text-3xl tabular-nums">{total}</strong><span className="text-xs text-muted-foreground">liquidaciones</span></div></div><div className="min-w-40 flex-1 space-y-4">{states.map(s=><Link to={liquidationsPath} key={s.key} className="flex items-center gap-3 rounded-lg hover:bg-muted"><span className="h-8 w-1 rounded-full" style={{background:s.color}}/><div className="flex-1"><p className="text-xs">{s.label}</p><p className="text-xs text-muted-foreground">{money(l[s.key].amount)}</p></div><strong className="text-xl tabular-nums">{l[s.key].count}</strong></Link>)}</div></div><p className="mt-5 text-xs text-muted-foreground">Los vouchers presentados esperan revisión; no equivalen a liquidaciones aprobadas.</p></article>}
   </section>
   {e&&<section className="overflow-hidden rounded-2xl border bg-card"><div className="flex items-center justify-between border-b px-5 py-4"><h2 className="text-sm font-semibold">Últimas emisiones</h2><Link to={emissionsPath} className="text-xs text-emerald-600 hover:underline">Ver todas</Link></div>{e.recent.length?<div className="overflow-x-auto"><table className="w-full text-left text-sm"><thead className="bg-muted/30 text-xs text-muted-foreground"><tr><th className="px-5 py-3">Certificado</th><th className="px-5 py-3">Programa</th><th className="px-5 py-3">Emisión</th><th className="px-5 py-3 text-right">Importe</th></tr></thead><tbody>{e.recent.map(r=><tr key={r.code} className="border-t"><td className="px-5 py-3 font-medium">{r.code}</td><td className="px-5 py-3">{r.plan}</td><td className="whitespace-nowrap px-5 py-3">{shortDate(r.date)}</td><td className="px-5 py-3 text-right tabular-nums">{money(r.amount)}</td></tr>)}</tbody></table></div>:<p className="p-5 text-sm text-muted-foreground">Todavía no hay emisiones en tu ámbito.</p>}</section>}
   {!e&&!l&&<p className="rounded-xl border p-5 text-sm text-muted-foreground">Utiliza el menú para acceder a tus opciones autorizadas.</p>}
   {(e||l)&&<p className="text-xs text-muted-foreground">Datos reales de tu ámbito comercial. No incluye pruebas ni anulaciones.</p>}
  </>}
 </main>;
}
