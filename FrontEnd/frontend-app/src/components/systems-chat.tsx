import { lazy, Suspense, useCallback, useEffect, useRef, useState } from 'react';
import { MessageCircle } from 'lucide-react';
import { useAuth } from '@/context/AuthContext';
import api from '@/lib/api';
import { Button } from '@/components/ui/button';
import { Dialog, DialogContent, DialogDescription, DialogTitle } from '@/components/ui/dialog';
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover';
import { Input } from '@/components/ui/input';

const SupportChatPane = lazy(() => import('./support-chat-pane').then(module => ({ default: module.SupportChatPane })));
type Contact = { id: number; name: string; state?: string; avatar_url?: string | null; unread: number };
type Directory = { operators: Contact[]; general_unread: number; unread: number };
type Target = { base: string; title: string; personal: boolean };

export function SystemsChat() {
  const { user, impersonation } = useAuth();
  if (!user || user.requiere_cambio_clave || impersonation?.active) return null;
  return <SystemsChatSession key={user.id} />;
}

function SystemsChatSession() {
  const [open, setOpen] = useState(false);
  const [directory, setDirectory] = useState<Directory | null>(null);
  const [error, setError] = useState('');
  const [search, setSearch] = useState('');
  const [target, setTarget] = useState<Target | null>(null);
  const busy = useRef(false);
  const controller = useRef<AbortController | null>(null);

  const refresh = useCallback(async () => {
    if (busy.current || document.hidden || !controller.current) return;
    busy.current = true;
    const signal = controller.current.signal;
    try {
      const { data } = await api.get<Directory>('/support-chat/contacts', { signal, timeout: 8000 });
      if (!signal.aborted) { setDirectory(data); setError(''); }
    } catch (cause) {
      if (!signal.aborted) {
        const detail = (cause as { response?: { data?: { detail?: string } } }).response?.data?.detail;
        setError(detail || 'No se pudo actualizar Sistemas. Vuelve a intentar.');
        // Keep names, but never present stale presence as current.
        setDirectory(previous => previous ? { ...previous, operators: previous.operators.map(person => ({ ...person, state: undefined })) } : null);
      }
    } finally { busy.current = false; }
  }, []);

  useEffect(() => {
    const lifetime = new AbortController();
    controller.current = lifetime;
    return () => { lifetime.abort(); controller.current = null; };
  }, []);

  useEffect(() => {
    let timer: ReturnType<typeof setTimeout>;
    let stopped = false;
    let pending = false;
    const pulse = async () => {
      if (pending || stopped) return;
      clearTimeout(timer);
      pending = true;
      try {
        if (!document.hidden && controller.current) await api.post('/support-chat/presence', {}, { signal: controller.current.signal, timeout: 8000 });
      } catch { /* The directory displays connection errors; presence expires on its own. */ }
      finally { pending = false; if (!stopped) timer = setTimeout(pulse, 20000); }
    };
    void pulse();
    document.addEventListener('visibilitychange', pulse);
    window.addEventListener('focus', pulse);
    return () => { stopped = true; clearTimeout(timer); document.removeEventListener('visibilitychange', pulse); window.removeEventListener('focus', pulse); };
  }, []);

  useEffect(() => {
    // One request at a time, including focus and visibility recovery.
    void refresh();
    const timer = setInterval(() => void refresh(), open ? 3000 : 20000);
    document.addEventListener('visibilitychange', refresh);
    window.addEventListener('focus', refresh);
    return () => { clearInterval(timer); document.removeEventListener('visibilitychange', refresh); window.removeEventListener('focus', refresh); };
  }, [open, refresh]);

  const choose = (person?: Contact) => {
    setTarget(person ? { base: `/support-chat/direct/${person.id}`, title: person.name, personal: true } : { base: '/support-chat', title: 'Soporte Sistemas', personal: false });
    setOpen(false);
  };
  const connected = directory?.operators.some(person => person.state === 'conectado');
  const known = !!directory && !error && directory.operators.every(person => ['conectado', 'desconectado'].includes(person.state || ''));
  const status = (state?: string) => state === 'conectado' ? 'Conectado' : state === 'desconectado' ? 'Desconectado' : 'Sin actualizar';
  const badge = (count: number) => count > 0 ? <span className="rounded-full bg-primary px-1.5 text-xs text-primary-foreground">{count}</span> : null;

  return <>
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild><Button variant="ghost" size="sm" aria-label={`Chat · Sistemas${directory?.unread ? `, ${directory.unread} sin leer` : ''}`} title="Chat · Sistemas"><MessageCircle className="size-4" /><span className="hidden sm:inline">Chat</span>{badge(directory?.unread || 0)}</Button></PopoverTrigger>
      <PopoverContent align="end" className="w-[min(340px,calc(100vw-2rem))] p-2">
        <p className="px-2 py-1 text-sm font-semibold">Sistemas · Virtual IA</p>
        <Input aria-label="Buscar en Sistemas" placeholder="Buscar integrante…" value={search} onChange={event => setSearch(event.target.value)} />
        {error && <p role="alert" className="p-2 text-xs text-destructive">{error} <button type="button" className="underline" onClick={() => void refresh()}>Reintentar</button></p>}
        {!directory && !error && <p role="status" className="p-2 text-xs">Cargando Sistemas…</p>}
        {directory && <div className="max-h-80 overflow-y-auto py-1">
          <button type="button" onClick={() => choose()} className="flex w-full items-center gap-2 rounded p-2 text-left text-sm hover:bg-muted"><MessageCircle className="size-5 shrink-0" /><span className="min-w-0 flex-1 truncate">Soporte Sistemas</span>{badge(directory.general_unread)}<span className="text-[10px] text-muted-foreground">{known ? connected ? 'Conectado' : 'Desconectado' : 'Sin actualizar'}</span></button>
          {directory.operators.filter(person => person.name.toLocaleLowerCase().includes(search.toLocaleLowerCase())).map(person => <button key={person.id} type="button" onClick={() => choose(person)} className="flex w-full items-center gap-2 rounded p-2 text-left text-sm hover:bg-muted">
            {person.avatar_url ? <img src={person.avatar_url} alt="" className="size-7 shrink-0 rounded-full object-cover" /> : <span className="flex size-7 shrink-0 items-center justify-center rounded-full bg-muted text-xs">{person.name.slice(0, 2).toUpperCase()}</span>}
            <span title={person.name} className="min-w-0 flex-1 truncate">{person.name}</span>{badge(person.unread)}<span className={`text-[10px] ${person.state === 'conectado' ? 'text-green-600' : 'text-muted-foreground'}`}>{status(person.state)}</span>
          </button>)}
          {!directory.operators.length && <p className="p-2 text-xs text-muted-foreground">No hay integrantes disponibles.</p>}
        </div>}
      </PopoverContent>
    </Popover>
    <Dialog open={!!target} onOpenChange={value => { if (!value) setTarget(null); }}>
      <DialogContent className="flex h-[min(720px,90dvh)] max-w-xl flex-col gap-0 overflow-hidden p-0 pt-8">
        <DialogTitle className="sr-only">{target?.title || 'Chat de Sistemas'}</DialogTitle><DialogDescription className="sr-only">Conversación de ABISSOL con Virtual IA.</DialogDescription>
        {target && <Suspense fallback={<p className="p-4">Cargando conversación…</p>}><SupportChatPane key={target.base} {...target} onRead={() => void refresh()} /></Suspense>}
      </DialogContent>
    </Dialog>
  </>;
}
