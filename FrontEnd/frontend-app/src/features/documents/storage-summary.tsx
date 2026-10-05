import { useState } from 'react';
import { toast } from 'sonner';
import api from '@/lib/api';
import { apiErrorMessage } from '@/lib/api-error';
import { ActionButton } from '@/components/action-button';
import { Sheet,SheetContent,SheetHeader,SheetTitle,SheetDescription,SheetBody } from '@/components/ui/sheet';
type Usage={active:number;trash:number;versions:number;bytes:number;history_bytes:number;trash_bytes:number;duplicate_copies:number;duplicate_bytes:number};
const size=(n:number)=>`${(n/1024/1024).toLocaleString('es-PE',{maximumFractionDigits:2})} MB`;
export function StorageSummary(){
  const [data,setData]=useState<Usage|null>(null);const [open,setOpen]=useState(false);const [busy,setBusy]=useState(false);
  return <><ActionButton tone="info" size="sm" disabled={busy} onClick={async()=>{setBusy(true);try{setData((await api.get('/documentos/almacenamiento')).data);setOpen(true);}catch(e){toast.error(apiErrorMessage(e));}finally{setBusy(false);}}}>Mi almacenamiento</ActionButton><Sheet open={open} onOpenChange={setOpen}><SheetContent><SheetHeader><SheetTitle>Mi almacenamiento</SheetTitle><SheetDescription>Uso registrado de tus archivos y versiones, incluida Papelera.</SheetDescription></SheetHeader><SheetBody className="space-y-4">{data&&<><dl className="grid grid-cols-2 gap-3"><dt>Archivos activos</dt><dd>{data.active}</dd><dt>En Papelera</dt><dd>{data.trash}</dd><dt>Versiones conservadas</dt><dd>{data.versions}</dd><dt>Total</dt><dd>{size(data.bytes)}</dd><dt>Versiones anteriores</dt><dd>{size(data.history_bytes)}</dd><dt>Papelera, todas las versiones</dt><dd>{size(data.trash_bytes)}</dd><dt>Copias con contenido idéntico</dt><dd>{data.duplicate_copies} · {size(data.duplicate_bytes)}</dd></dl><p className="text-sm text-muted-foreground">Las categorías pueden coincidir: una versión anterior también puede estar en Papelera. Las copias idénticas se reconocen por su contenido; pueden tener propósitos distintos.</p><p className="text-sm">Revisa tus archivos antes de enviarlos a Papelera. La política de eliminación se configura desde Papelera y permanece como la hayas definido. Este resumen no elimina ni fusiona documentos.</p></>}</SheetBody></SheetContent></Sheet></>;
}
