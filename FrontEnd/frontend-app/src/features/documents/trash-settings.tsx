import {useState} from 'react';
import {Settings2} from 'lucide-react';
import {toast} from 'sonner';
import api from '@/lib/api';
import {apiErrorMessage} from '@/lib/api-error';
import {Button} from '@/components/ui/button';
import {Input} from '@/components/ui/input';
import {Label} from '@/components/ui/label';
import {Sheet,SheetContent,SheetHeader,SheetTitle,SheetDescription,SheetBody,SheetFooter} from '@/components/ui/sheet';

export function TrashSettings(){
  const [open,setOpen]=useState(false),[days,setDays]=useState('0'),[busy,setBusy]=useState(false);
  const valid=/^\d+$/.test(days)&&Number(days)<=3650;
  async function load(){setBusy(true);try{const {data}=await api.get('/documentos/papelera/configuracion');setDays(String(data.days));setOpen(true);}catch(error){toast.error(apiErrorMessage(error,'No se pudo cargar la configuración'));}finally{setBusy(false);}}
  async function save(){setBusy(true);try{await api.put('/documentos/papelera/configuracion',{days:Number(days)});toast.success('Configuración de Papelera guardada');setOpen(false);}catch(error){toast.error(apiErrorMessage(error,'No se pudo guardar'));}finally{setBusy(false);}}
  return <><Button variant="ghost" size="icon" title="Configurar Papelera" aria-label="Configurar Papelera" disabled={busy} onClick={()=>void load()}><Settings2 className="size-4"/></Button><Sheet open={open} onOpenChange={value=>{if(!busy)setOpen(value);}}><SheetContent><SheetHeader><SheetTitle>Mi papelera</SheetTitle><SheetDescription>Conservación de tus archivos eliminados.</SheetDescription></SheetHeader><SheetBody className="space-y-4"><Label htmlFor="trash-days">Días antes de eliminar definitivamente</Label><Input id="trash-days" type="number" min={0} max={3650} value={days} onChange={event=>setDays(event.target.value)}/><p className="text-sm text-muted-foreground">0: no eliminar automáticamente. Entre 1 y 3650 días desde que cada archivo entró en Papelera. Se revisa cada hora mientras el servidor esté activo.</p><p className="text-sm">Al guardar un plazo, se eliminarán también los archivos que ya lo hayan superado, con todas sus versiones y anotaciones. No se podrán recuperar. Solo afecta a tus archivos; las carpetas se conservan.</p></SheetBody><SheetFooter><Button disabled={!valid||busy} onClick={()=>void save()}>{busy?'Guardando…':Number(days)>0?'Guardar y activar eliminación automática':'Guardar'}</Button></SheetFooter></SheetContent></Sheet></>;
}
