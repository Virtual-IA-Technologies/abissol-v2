import { useState } from 'react';
import { toast } from 'sonner';
import api from '@/lib/api';
import { apiErrorMessage } from '@/lib/api-error';
import { ActionButton } from '@/components/action-button';
import { Sheet,SheetContent,SheetHeader,SheetTitle,SheetDescription,SheetBody } from '@/components/ui/sheet';
type Status={eligible:number;days:number;can_archive:boolean;files:{name:string;bytes:number}[]};

export function AuditStorage(){
  const [open,setOpen]=useState(false);const [data,setData]=useState<Status|null>(null);const [busy,setBusy]=useState(false);const [confirm,setConfirm]=useState(false);
  const load=async()=>{setBusy(true);try{setData((await api.get('/auditoria/archivo')).data);setOpen(true);}catch(e){toast.error(apiErrorMessage(e));}finally{setBusy(false);}};
  return <><ActionButton tone="info" disabled={busy} onClick={()=>void load()}>Conservación</ActionButton><Sheet open={open} onOpenChange={v=>{setOpen(v);setConfirm(false);}}><SheetContent><SheetHeader><SheetTitle>Conservación de Auditoría</SheetTitle><SheetDescription>Menos eventos repetidos, con historial verificable.</SheetDescription></SheetHeader><SheetBody className="space-y-4">
    <p className="text-sm">Los cambios funcionales confirmados ya no generan además un HTTP exitoso. Las renovaciones de sesión y lecturas de avisos tampoco se acumulan. Los errores y cambios de negocio mantienen su evidencia.</p>
    <p className="text-sm">Se pueden archivar HTTP exitosos de más de {data?.days||90} días, en lotes de hasta 1.000. El archivo comprimido se verifica antes de retirar esas filas de la tabla. Los cambios funcionales y errores se conservan en la base.</p>
    <p className="font-medium">{data?.eligible||0} eventos técnicos elegibles</p>
    {data?.can_archive&&data.eligible>0&&<>{confirm?<div className="space-y-2 rounded border p-3"><p>Se archivará el siguiente lote. Descarga y respalda los archivos junto con la base.</p><ActionButton tone="edit" disabled={busy} onClick={async()=>{setBusy(true);try{const r=await api.post('/auditoria/archivo',null,{params:{confirmed:true}});toast.success(`${r.data.archived} eventos archivados`);setConfirm(false);await load();}catch(e){toast.error(apiErrorMessage(e));}finally{setBusy(false);}}}>Confirmar archivo</ActionButton></div>:<ActionButton tone="edit" onClick={()=>setConfirm(true)}>Archivar lote antiguo</ActionButton>}</>}
    <h3 className="font-semibold">Archivos conservados</h3>{!data?.files.length&&<p className="text-sm text-muted-foreground">Todavía no hay archivos.</p>}{data?.files.map(f=><div className="space-y-1 border-b pb-2" key={f.name}><p className="break-all text-xs">{f.name} · {(f.bytes/1024).toFixed(1)} KB</p><ActionButton tone="info" onClick={async()=>{try{const r=await api.get(`/auditoria/archivo/${encodeURIComponent(f.name)}`,{responseType:'blob'});const url=URL.createObjectURL(r.data);const a=document.createElement('a');a.href=url;a.download=f.name;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);}catch(e){toast.error(apiErrorMessage(e));}}}>Descargar historial</ActionButton></div>)}
  </SheetBody></SheetContent></Sheet></>;
}
