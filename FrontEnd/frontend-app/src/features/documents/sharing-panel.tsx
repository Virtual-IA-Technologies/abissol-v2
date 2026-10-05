import { useEffect, useState } from 'react';
import { Share2, Link, UserRound } from 'lucide-react';
import { toast } from 'sonner';
import api from '@/lib/api';
import { apiErrorMessage } from '@/lib/api-error';
import { ActionButton } from '@/components/action-button';
import { SearchableSelect } from '@/components/searchable-select';
import { ExternalLinks } from './external-links';
import { documents, type Detail } from './api';

export function SharingPanel({ document, onChange, onRemove }: { document: Detail; onChange: (detail: Detail) => void; onRemove: (id: number, name: string) => void }) {
  const [people, setPeople] = useState<{ username: string; name: string }[]>([]);
  const [recipient, setRecipient] = useState('');
  const [busy, setBusy] = useState(false);
  const [mode, setMode] = useState<'user'|'public'>('user');
  useEffect(() => {
    const controller = new AbortController();
    void api.get<{ username: string; name: string }[]>(`/documentos/${document.id}/destinatarios`, { signal: controller.signal })
      .then(result => setPeople(result.data)).catch(error => { if (!controller.signal.aborted) toast.error(apiErrorMessage(error, 'No se pudieron consultar los usuarios')); });
    return () => controller.abort();
  }, [document.id]);
  const share = async () => {
    setBusy(true);
    try { onChange(await documents.share(document, recipient)); setRecipient(''); toast.success('Documento compartido'); }
    catch (error) { toast.error(apiErrorMessage(error, 'No se pudo compartir')); }
    finally { setBusy(false); }
  };
  return <section id="document-sharing" className="space-y-3 rounded-xl border p-4">
    <h2 className="flex items-center gap-2 font-medium"><Share2 className="size-4" />Compartir documento</h2>
    <div role="tablist" aria-label="Forma de compartir" className="flex gap-2"><button type="button" role="tab" aria-selected={mode==='user'} className={`flex items-center rounded-lg border px-3 py-2 text-sm ${mode==='user'?'bg-muted':''}`} onClick={()=>setMode('user')}><UserRound className="mr-2 size-4" />Usuario específico</button><button type="button" role="tab" aria-selected={mode==='public'} className={`flex items-center rounded-lg border px-3 py-2 text-sm ${mode==='public'?'bg-muted':''}`} onClick={()=>setMode('public')}><Link className="mr-2 size-4" />URL pública</button></div>
      {mode==='user'?<div role="tabpanel" className="space-y-3 pt-2"><p className="text-xs text-muted-foreground">Comparte este archivo en modo lectura. No se comparte la carpeta; el usuario necesita acceso a Documentos.</p>
        <div className="flex flex-wrap gap-2"><div className="min-w-48 flex-1"><SearchableSelect aria-label="Usuario para compartir" value={recipient} onValueChange={setRecipient} disabled={busy} options={people.map(person => ({ value: person.username, label: person.name, keywords: person.username }))} /></div><ActionButton tone="new" disabled={busy || !recipient} onClick={() => void share()}>Compartir</ActionButton></div>
        {document.shares.map(item => <div key={item.id} className="flex items-center justify-between gap-3 rounded-lg border p-3 text-sm"><span>{item.name}</span><ActionButton tone="delete" size="sm" disabled={busy} onClick={() => onRemove(item.id, item.name)}>Retirar acceso</ActionButton></div>)}
      </div>:<div role="tabpanel" className="pt-2"><ExternalLinks document={document} /></div>}
  </section>;
}
