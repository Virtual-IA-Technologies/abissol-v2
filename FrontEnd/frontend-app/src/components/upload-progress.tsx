import { useEffect, useState } from 'react';
type Transfer = { id: string; state: string; loaded: number; total?: number };

export function UploadProgress() {
  const [transfers, setTransfers] = useState<Record<string, Transfer>>({});
  useEffect(() => {
    const update = (event: Event) => {
      const transfer = (event as CustomEvent<Transfer>).detail;
      setTransfers(current => {
        const next = { ...current };
        if (transfer.state === 'finished') delete next[transfer.id];
        else next[transfer.id] = transfer;
        return next;
      });
    };
    window.addEventListener('abissol:upload', update);
    return () => window.removeEventListener('abissol:upload', update);
  }, []);
  return <aside aria-live="polite" className="fixed bottom-4 right-4 z-[200] grid w-80 max-w-[calc(100vw-2rem)] gap-2">
    {Object.values(transfers).map(item => {
      const percent = item.total ? Math.min(100, Math.floor(100 * item.loaded / item.total)) : 0;
      return <div key={item.id} className="rounded-xl border bg-background p-4 shadow-lg">
        <p className="text-sm font-medium">{item.state === 'processing' ? 'Subida completa · Guardando…' : `Subiendo archivo · ${percent}%`}</p>
        <progress aria-label="Progreso de subida" value={percent} max={100} className="mt-2 h-2 w-full accent-primary" />
        <p className="mt-1 text-xs text-muted-foreground">{(item.loaded / 1048576).toFixed(1)} MB{item.total ? ` de ${(item.total / 1048576).toFixed(1)} MB` : ''}</p>
      </div>;
    })}
  </aside>;
}
