import {useEffect,useState} from 'react';
import {Link,Copy,Pencil} from 'lucide-react';
import {toast} from 'sonner';
import api,{API_ROOT} from '@/lib/api';
import {apiErrorMessage} from '@/lib/api-error';
import {Button} from '@/components/ui/button';
import {Input} from '@/components/ui/input';
import {Label} from '@/components/ui/label';
import {SearchableSelect} from '@/components/searchable-select';
import type {Detail} from './api';
type ExternalLink={id:number;number:number;expires_at:string;revoked_at:string|null};
const localDate=(date:Date)=>new Date(date.getTime()-date.getTimezoneOffset()*60000).toISOString().slice(0,16);
const initialExpiry=()=>localDate(new Date(Date.now()+7*86400000));
const validDate=(value:string)=>Number.isFinite(new Date(value).getTime())&&new Date(value).getTime()>Date.now();
export function ExternalLinks({document}:{document:Detail}) {
  const [items,setItems]=useState<ExternalLink[]>([]),[version,setVersion]=useState(String(document.current_version)),[url,setUrl]=useState(''),[busy,setBusy]=useState(false),[refresh,setRefresh]=useState(0);
  const [expires,setExpires]=useState(initialExpiry),[editing,setEditing]=useState<number|null>(null),[changedDate,setChangedDate]=useState('');
  useEffect(()=>{let active=true;void api.get<ExternalLink[]>(`/documentos/${document.id}/enlaces`).then(r=>{if(active)setItems(r.data);}).catch(()=>toast.error('No se pudieron consultar los enlaces'));return()=>{active=false;};},[document.id,refresh]);
  const create=async()=>{setBusy(true);try{const {data}=await api.post<{token:string}>(`/documentos/${document.id}/versiones/${version}/enlaces`,{expires_at:new Date(expires).toISOString()});setUrl(`${API_ROOT}/documentos/publico/archivo?token=${encodeURIComponent(data.token)}`);setRefresh(v=>v+1);}catch(error){toast.error(apiErrorMessage(error,'No se pudo crear el enlace'));}finally{setBusy(false);}};
  const update=async(id:number)=>{setBusy(true);try{await api.patch(`/documentos/${document.id}/enlaces/${id}`,{expires_at:new Date(changedDate).toISOString()});setEditing(null);setRefresh(v=>v+1);toast.success('Vencimiento actualizado; el enlace sigue siendo el mismo');}catch(error){toast.error(apiErrorMessage(error,'No se pudo actualizar el vencimiento'));}finally{setBusy(false);}};
  return <div className="space-y-3">
    <h2 className="font-medium">Enlace externo</h2><p className="text-xs text-muted-foreground">Cualquier persona con el enlace podrá descargar la versión elegida hasta el vencimiento. Puedes cambiar la fecha o retirarlo antes.</p>
    <div className="grid gap-3 sm:grid-cols-2"><div className="space-y-2"><Label>Versión</Label><SearchableSelect disabled={busy} value={version} onValueChange={value=>{setVersion(value);setUrl('');}} options={document.versions.map(v=>({value:String(v.number),label:`Versión ${v.number}`}))}/></div><div className="space-y-2"><Label htmlFor="link-expiry">Vence el enlace</Label><Input id="link-expiry" type="datetime-local" disabled={busy} value={expires} onChange={e=>setExpires(e.target.value)}/></div></div>
    <p className="text-xs text-muted-foreground">Fecha y hora de tu dispositivo.</p><Button variant="outline" disabled={busy||!validDate(expires)} onClick={()=>void create()}><Link className="size-4"/>Crear enlace</Button>
    {url&&<div className="flex gap-2"><Input readOnly aria-label="Enlace externo creado" value={url}/><Button variant="ghost" aria-label="Copiar enlace" onClick={()=>void navigator.clipboard.writeText(url).then(()=>toast.success('Enlace copiado')).catch(()=>toast.error('Selecciona y copia el enlace del campo'))}><Copy className="size-4"/></Button></div>}
    {items.map(item=><div key={item.id} className="space-y-2 rounded border p-3 text-xs"><div className="flex flex-wrap items-center justify-between gap-2"><span>v{item.number} · {item.revoked_at?'Retirado':`${new Date(item.expires_at)<new Date()?'Venció':'Vence'} ${new Date(item.expires_at).toLocaleString('es-PE')}`}</span>{!item.revoked_at&&<div className="flex gap-1"><Button variant="ghost" size="sm" disabled={busy} onClick={()=>{setEditing(item.id);setChangedDate(localDate(new Date(item.expires_at)));}}><Pencil className="size-3"/>Vencimiento</Button><Button variant="ghost" size="sm" disabled={busy} onClick={async()=>{setBusy(true);try{await api.delete(`/documentos/${document.id}/enlaces/${item.id}`);setUrl('');setEditing(null);setRefresh(v=>v+1);}catch(error){toast.error(apiErrorMessage(error,'No se pudo retirar'));}finally{setBusy(false);}}}>Retirar</Button></div>}</div>
    {editing===item.id&&<div className="space-y-2"><Label htmlFor={`expiry-${item.id}`}>Nuevo vencimiento</Label><Input id={`expiry-${item.id}`} type="datetime-local" disabled={busy} value={changedDate} onChange={e=>setChangedDate(e.target.value)}/>{new Date(item.expires_at)<new Date()&&<p>Guardar una fecha futura volverá a habilitar este enlace vencido.</p>}<div className="flex gap-2"><Button size="sm" disabled={busy||!validDate(changedDate)} onClick={()=>void update(item.id)}>Guardar</Button><Button variant="ghost" size="sm" disabled={busy} onClick={()=>setEditing(null)}>Cancelar</Button></div></div>}</div>)}
  </div>;
}
