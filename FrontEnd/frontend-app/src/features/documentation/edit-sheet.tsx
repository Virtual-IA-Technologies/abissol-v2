import { lazy, Suspense, useState } from "react";
import { toast } from "sonner";
import { Sheet, SheetBody, SheetContent, SheetDescription, SheetFooter, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Button } from "@/components/ui/button";
import { ActionButton } from "@/components/action-button";
import { SearchableSelect } from "@/components/searchable-select";
import { ConfirmActionDialog } from "@/components/confirm-action-dialog";
import { docs, errorMessage, type Article, type ArticleWrite } from "./api";
const Editor = lazy(() => import("./editor"));
const options = (items: string[][]) => items.map(([value, label]) => ({value, label}));

export default function EditSheet({ article, onClose, onSaved }: { article: Article | null; onClose: () => void; onSaved: (article: Article) => void }) {
  const [form, setForm] = useState<ArticleWrite>({titulo: article?.titulo || "", resumen: article?.resumen || "", categoria: article?.categoria || "General", audiencia: article?.audiencia || "general", estado: article?.estado || "borrador", contenido: article?.contenido || "", motivo: article ? "" : "Creación del artículo", version: article?.version});
  const [busy, setBusy] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [dirty, setDirty] = useState(false);
  const [mode, setMode] = useState<"visual" | "markdown">("visual");
  const field = (name: keyof ArticleWrite, value: string) => { setDirty(true); setForm(f => ({...f, [name]: value})); };
  const save = async () => {
    if (!form.titulo.trim() || form.motivo.trim().length < 3) { toast.error("Completa el título y un motivo de al menos 3 caracteres."); return; }
    setBusy(true);
    try { const row = article ? await docs.update(article.id, form) : await docs.create(form); toast.success("Artículo guardado con una nueva revisión"); onSaved(row); }
    catch (error) { toast.error(errorMessage(error)); } finally { setBusy(false); }
  };
  const close = () => { if (!dirty && !busy && !uploading) onClose(); };
  return <Sheet open onOpenChange={open => { if (!open) close(); }}><SheetContent showCloseButton={!dirty} className="w-full sm:max-w-4xl"><SheetHeader><SheetTitle>{article ? "Editar artículo" : "Nuevo artículo"}</SheetTitle><SheetDescription>{article ? `Versión ${article.version}. Cada guardado conserva autor, motivo y cambios.` : "Empieza con un borrador. Después podrás adjuntar archivos y capturas."}</SheetDescription></SheetHeader>
    <SheetBody className="space-y-5">
      <div className="space-y-2"><Label htmlFor="doc-title">Título</Label><Input id="doc-title" maxLength={180} value={form.titulo} onChange={e => field("titulo", e.target.value)} /></div>
      <div className="space-y-2"><Label htmlFor="doc-summary">Descripción breve</Label><Input id="doc-summary" maxLength={500} value={form.resumen} onChange={e => field("resumen", e.target.value)} /></div>
      <div className="grid gap-4 sm:grid-cols-3">
        <div className="space-y-2"><Label htmlFor="doc-category">Categoría</Label><Input id="doc-category" maxLength={100} value={form.categoria} onChange={e => field("categoria", e.target.value)} /></div>
        <div className="space-y-2"><Label>Audiencia</Label><SearchableSelect aria-label="Audiencia" value={form.audiencia} onValueChange={v => field("audiencia", v)} options={options([["general", "Manual de uso"], ["tecnica", "Técnica · Programadores"], ["interna", "Interna · Programadores"]])} /></div>
        <div className="space-y-2"><Label>Estado</Label><SearchableSelect aria-label="Estado del artículo" value={form.estado} onValueChange={v => field("estado", v)} options={options([["borrador", "Borrador"], ["publicado", "Publicado"], ["archivado", "Archivado"]])} /></div>
      </div>
      <div className="flex items-center justify-between"><Label>Contenido</Label><Button type="button" variant="ghost" size="sm" onClick={() => setMode(mode === "visual" ? "markdown" : "visual")}>{mode === "visual" ? "Ver Markdown" : "Editor visual"}</Button></div>
      {mode === "visual" ? <Suspense fallback={<p>Cargando editor…</p>}><Editor content={form.contenido} articleId={article?.id ?? null} onChange={v => field("contenido", v)} onBusy={setUploading} /></Suspense> : <textarea aria-label="Contenido Markdown" className="min-h-80 w-full rounded-md border bg-background p-3 font-mono text-sm" maxLength={200000} value={form.contenido} onChange={e => field("contenido", e.target.value)} />}
      <div className="space-y-2"><Label htmlFor="doc-reason">Motivo del cambio</Label><Input id="doc-reason" maxLength={500} value={form.motivo} onChange={e => field("motivo", e.target.value)} placeholder="Qué cambiaste y por qué" /></div>
    </SheetBody><SheetFooter>
      {dirty ? <ConfirmActionDialog title="Descartar el borrador" description="Los cambios sin guardar se perderán." confirmLabel="Descartar" onConfirm={onClose}><Button variant="outline" disabled={busy || uploading}>Cancelar</Button></ConfirmActionDialog> : <Button variant="outline" onClick={onClose} disabled={busy || uploading}>Cancelar</Button>}
      <ActionButton tone="edit" onClick={() => void save()} disabled={busy || uploading}>{busy ? "Guardando…" : "Guardar revisión"}</ActionButton>
    </SheetFooter></SheetContent></Sheet>;
}
