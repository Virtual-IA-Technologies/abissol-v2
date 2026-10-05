import { useCallback, useEffect, useState } from 'react';
import { Bell, ExternalLink, Check, Trash2 } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { AlertDialog, AlertDialogContent, AlertDialogHeader, AlertDialogTitle, AlertDialogDescription, AlertDialogFooter, AlertDialogCancel, AlertDialogAction } from '@/components/ui/alert-dialog';
import { toast } from 'sonner';
import { ActionButton } from '@/components/action-button';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import { SearchableSelect } from '@/components/searchable-select';
import { ConfirmActionDialog } from '@/components/confirm-action-dialog';
import { ListPagination } from '@/components/list-pagination';
import { RowActionsMenu } from '@/components/row-actions-menu';
import { RecordContextMenu } from '@/components/record-context-menu';
import { useDoubleClickPreference } from '@/lib/use-double-click-preference';
import type { PageSize } from '@/lib/use-list-pagination';
import { formatLimaDateTime } from '@/lib/dates';
import { notificationsAPI, type InboxResult } from './api';
import { useNotifications } from './notification-context';
import type { NotificationItem } from './types';

export function NotificationInbox() {
  const navigate = useNavigate();
  const { refresh, items: live, unread } = useNotifications();
  const liveId = live[0]?.id;
  const [search, setSearch] = useState(''), [source, setSource] = useState(''), [severity, setSeverity] = useState('');
  const [page, setPage] = useState(1), [limit, setLimit] = useState<PageSize>(25), [unreadOnly, setUnreadOnly] = useState(false);
  const [data, setData] = useState<InboxResult>({ items: [], unread: 0, total: 0, sources: [] });
  const [selected, setSelected] = useState<number[]>([]), [loading, setLoading] = useState(false), [revision, setRevision] = useState(0);
  const [doubleClick, setDoubleClick] = useDoubleClickPreference('notificaciones', ['open','read'] as const, 'open');
  const [removing,setRemoving]=useState<number|null>(null),[deleting,setDeleting]=useState(false);
  const changed = useCallback(() => { setRevision(value => value+1); void refresh(); }, [refresh]);
  useEffect(() => { setPage(1); setSelected([]); }, [search, source, severity, unreadOnly, limit]);
  useEffect(() => {
    const controller = new AbortController();
    setLoading(true); setSelected([]);
    const timer = window.setTimeout(() => {
      void notificationsAPI.inbox({ page, limit: limit==='all'?200:limit, search, source, severity, unread_only: unreadOnly }, controller.signal)
        .then(result => { if (!controller.signal.aborted) { setData(result); if (page>1 && !result.items.length) setPage(Math.max(1,Math.ceil(result.total/(limit==='all'?200:limit)))); } })
        .catch(() => { if (!controller.signal.aborted) toast.error('No se pudo cargar el buzón'); })
        .finally(() => { if (!controller.signal.aborted) setLoading(false); });
    }, 180);
    return () => { clearTimeout(timer); controller.abort(); };
  }, [page, limit, search, source, severity, unreadOnly, revision, liveId, unread]);
  const read = async (item: NotificationItem, open=false) => {
    try { if (!item.read_at) await notificationsAPI.read(item.id); changed(); if (open && item.url) navigate(item.url); }
    catch { toast.error('El aviso ya no está disponible'); }
  };
  const remove = async (ids: number[]) => { await notificationsAPI.remove(ids); changed(); };
  return <section className="overflow-hidden rounded-xl border">
    <div className="space-y-3 border-b p-4"><div className="flex flex-wrap gap-2"><Input className="min-w-48 flex-1" value={search} onChange={event=>setSearch(event.target.value)} placeholder="Buscar aviso…" /><SearchableSelect value={source||'all'} onValueChange={value=>setSource(value==='all'?'':value)} options={[{value:'all',label:'Todas las fuentes'},...data.sources.map(name=>({value:name,label:name}))]} /><SearchableSelect value={severity||'all'} onValueChange={value=>setSeverity(value==='all'?'':value)} options={[{value:'all',label:'Todos los niveles'},{value:'info',label:'Información'},{value:'warning',label:'Advertencia'},{value:'critical',label:'Crítico'}]} /></div>
      <div className="flex flex-wrap items-center gap-2"><button className={`rounded-full border px-3 py-1 text-xs ${!unreadOnly?'bg-sky-50 text-sky-700':''}`} onClick={()=>setUnreadOnly(false)}>Todos</button><button className={`rounded-full border px-3 py-1 text-xs ${unreadOnly?'bg-sky-50 text-sky-700':''}`} onClick={()=>setUnreadOnly(true)}>No leídos ({data.unread})</button><span className="ml-auto text-xs text-muted-foreground">{data.total} avisos</span>{selected.length>0&&<ConfirmActionDialog title="Eliminar avisos" description={`Se retirarán ${selected.length} avisos de tu buzón.`} destructive confirmLabel="Eliminar" onConfirm={()=>remove(selected)}><ActionButton tone="delete" size="sm"><Trash2 />Eliminar ({selected.length})</ActionButton></ConfirmActionDialog>}</div>
      <ListPagination embedded page={page} pageSize={limit} totalItems={data.total} totalPages={Math.max(1,Math.ceil(data.total/(limit==='all'?200:limit)))} onPageChange={setPage} onPageSizeChange={setLimit} includeAll={false} />
    </div>
    {loading?<p className="p-10 text-center text-sm text-muted-foreground">Cargando avisos…</p>:data.items.length?<div className="divide-y">{data.items.map(item=>{
      const actions=[{label:'Abrir aviso',icon:ExternalLink,onSelect:()=>void read(item,true)},{label:'Marcar como leído',icon:Check,onSelect:()=>void read(item)},{label:'Eliminar aviso',icon:Trash2,destructive:true,onSelect:()=>setRemoving(item.id)}];
      const preference={value:doubleClick,choices:[{value:'open' as const,label:'Abrir aviso'},{value:'read' as const,label:'Marcar como leído'}],onChange:setDoubleClick};
      return <RecordContextMenu key={item.id} actions={actions} doubleClick={preference}><div title="Doble clic para abrir o marcar el aviso" onDoubleClick={event=>{if(!(event.target as HTMLElement).closest('button,input'))void read(item,doubleClick==='open');}} className={`flex items-start gap-3 p-4 ${item.read_at?'':'bg-sky-50/30 dark:bg-sky-950/20'}`}>
        <input type="checkbox" aria-label={`Seleccionar ${item.title}`} checked={selected.includes(item.id)} onChange={event=>setSelected(current=>event.target.checked?[...current,item.id]:current.filter(id=>id!==item.id))}/>
        <button onClick={()=>void read(item,true)} className="min-w-0 flex-1 text-left"><span className="flex flex-wrap items-center gap-2"><strong className="text-sm">{item.title}</strong><Badge variant="outline">{item.source}</Badge><Badge variant="outline">{item.severity==='critical'?'Crítico':item.severity==='warning'?'Advertencia':'Información'}</Badge></span><span className="mt-1 block text-sm text-muted-foreground">{item.message}</span><span className="mt-2 block text-xs text-muted-foreground">{formatLimaDateTime(item.created_at)}</span></button>
        <RowActionsMenu label={item.title} actions={actions} doubleClick={preference}/>
      </div></RecordContextMenu>;
    })}</div>:<div className="flex flex-col items-center gap-2 p-12 text-muted-foreground"><Bell/><p className="text-sm">No hay avisos con estos filtros.</p></div>}
    <AlertDialog open={removing!==null} onOpenChange={open=>{if(!open&&!deleting)setRemoving(null);}}><AlertDialogContent><AlertDialogHeader><AlertDialogTitle>Eliminar aviso</AlertDialogTitle><AlertDialogDescription>Se retirará de tu buzón personal.</AlertDialogDescription></AlertDialogHeader><AlertDialogFooter><AlertDialogCancel disabled={deleting}>Cancelar</AlertDialogCancel><AlertDialogAction disabled={deleting} onClick={async event=>{event.preventDefault();if(removing===null)return;setDeleting(true);try{await remove([removing]);setRemoving(null);}catch{toast.error('No se pudo eliminar el aviso');}finally{setDeleting(false);}}}>{deleting?'Eliminando…':'Eliminar'}</AlertDialogAction></AlertDialogFooter></AlertDialogContent></AlertDialog>
  </section>;
}
