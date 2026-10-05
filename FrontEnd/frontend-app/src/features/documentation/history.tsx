import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ConfirmActionDialog } from "@/components/confirm-action-dialog";
import { Sheet, SheetBody, SheetContent, SheetDescription, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { dateLabel, docs, errorMessage, type Article, type Revision, type RevisionDetail } from "./api";

export default function History({ article, onClose, onRestored }: { article: Article; onClose: () => void; onRestored: (article: Article) => void }) {
  const [rows, setRows] = useState<Revision[]>([]); const [page, setPage] = useState(1); const [total, setTotal] = useState(0);
  const [selected, setSelected] = useState<Revision | null>(null); const [detail, setDetail] = useState<RevisionDetail | null>(null); const [reason, setReason] = useState(""); const [error, setError] = useState("");
  useEffect(() => { let live = true; docs.history(article.id, page).then(r => { if (live) {setRows(r.items); setTotal(r.total);} }).catch(e => { if (live) setError(errorMessage(e)); }); return () => {live = false;}; }, [article.id, page]);
  useEffect(() => { let live = true; setDetail(null); if (selected) docs.revision(article.id, selected.id).then(r => {if (live) setDetail(r);}).catch(e => {if (live) setError(errorMessage(e));}); return () => {live = false;}; }, [article.id, selected]);
  return <Sheet open onOpenChange={open => { if (!open) onClose(); }}><SheetContent className="w-full sm:max-w-3xl"><SheetHeader><SheetTitle>Historial de cambios</SheetTitle><SheetDescription>{article.titulo} · {total} revisiones</SheetDescription></SheetHeader><SheetBody className="space-y-4">
    {error && <p role="alert" className="text-sm text-destructive">{error}</p>}
    <div className="space-y-1">{rows.map(row => <button key={row.id} onClick={() => setSelected(row)} className={`block w-full rounded-lg border p-3 text-left ${selected?.id === row.id ? "bg-muted" : "hover:bg-muted/50"}`}><span className="text-sm font-medium">v{row.version} · {row.autor}</span><span className="block text-xs text-muted-foreground">{dateLabel(row.creado_en)} · {row.motivo}</span></button>)}</div>
    {total > 20 && <div className="flex justify-between"><Button variant="ghost" disabled={page === 1} onClick={() => setPage(p => p - 1)}>Anterior</Button><Button variant="ghost" disabled={page * 20 >= total} onClick={() => setPage(p => p + 1)}>Siguiente</Button></div>}
    {detail && selected && <div className="space-y-3"><h3 className="font-medium">Cambios de la versión {selected.version}</h3><p className="text-xs">Campos: {detail.campos.join(", ")}</p>
      {detail.campos.filter(key => key !== "contenido").map(key => <p key={key} className="break-words text-xs"><strong>{key}:</strong> {String(detail.antes[key as keyof Article] ?? "—")} → {String(detail.despues[key as keyof Article] ?? "—")}</p>)}
      <pre className="max-h-96 overflow-auto rounded-lg bg-muted p-3 text-xs">{detail.diff || "Sin cambios en el cuerpo del artículo."}</pre>
      {article.origen !== "repositorio" && selected.version !== article.version && <><Input aria-label="Motivo de restauración" placeholder="Motivo para restaurar esta versión" value={reason} onChange={e => setReason(e.target.value)} maxLength={450} /><ConfirmActionDialog title="Restaurar revisión" description="Se creará una nueva revisión con este contenido, estado y audiencia. El historial se conserva." onConfirm={async () => { try { onRestored(await docs.restore(article.id, selected.id, article.version, reason)); toast.success("Revisión restaurada"); } catch (e) {toast.error(errorMessage(e));} }}><Button disabled={reason.trim().length < 3}>Restaurar versión {selected.version}</Button></ConfirmActionDialog></>}
    </div>}
  </SheetBody></SheetContent></Sheet>;
}
