import { useEffect, useRef, useState } from "react";
import { Paperclip, Search, Send, X } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ConfirmActionDialog } from "@/components/confirm-action-dialog";
import { useAuth } from "@/context/AuthContext";
import { attachmentPath, dateLabel, docs, errorMessage, saveBlob, type Article, type Attachment, type CommentAnchor, type DocComment } from "./api";
import { ProtectedImage } from "./markdown";
import { SearchHighlight } from "./search-highlight";

export default function Comments({ article, quote, onClearQuote, programmer, anchor, composerOnly = false, revision = 0, search = "", onChanged, onLocate }: { article: Article; quote: string; onClearQuote: () => void; programmer: boolean; anchor?: CommentAnchor | null; composerOnly?: boolean; revision?: number; search?: string; onChanged?: () => void; onLocate?: (row: DocComment) => void }) {
  const {user} = useAuth(); const picker = useRef<HTMLInputElement>(null); const composer = useRef<HTMLTextAreaElement>(null);
  useEffect(() => {if (composerOnly) composer.current?.focus({preventScroll: true});}, [composerOnly]);
  const [rows, setRows] = useState<DocComment[]>([]); const [page, setPage] = useState(1); const [total, setTotal] = useState(0);
  const [query, setQuery] = useState(""); const [loading, setLoading] = useState(false);
  useEffect(() => {setQuery(search);setPage(1);}, [search]);
  const [body, setBody] = useState(""); const [files, setFiles] = useState<Attachment[]>([]); const [busy, setBusy] = useState(false); const [reload, setReload] = useState(0); const [failed, setFailed] = useState(false);
  useEffect(() => { if (composerOnly) return; let live = true; setFailed(false); setLoading(true); const timer = setTimeout(() => {void docs.comments(article.id, page, query).then(r => { if (live) { setRows(r.items); setTotal(r.total); } }).catch(() => { if (live) setFailed(true); }).finally(() => {if (live) setLoading(false);});}, 180); return () => { live = false; clearTimeout(timer); }; }, [article.id, page, reload, revision, composerOnly, query]);
  const upload = async (file: File) => {
    if (busy || files.length >= 5) return;
    setBusy(true); try { const result = await docs.upload(article.id, file, "comentario"); setFiles(old => [...old, result]); }
    catch (error) { toast.error(errorMessage(error)); } finally { setBusy(false); }
  };
  const send = async () => { setBusy(true); try { await docs.comment(article.id, {contenido: body, cita: quote, ancla: anchor, version_articulo: article.version, adjuntos: files.map(f => f.id)}); setBody(""); setFiles([]); onClearQuote(); setPage(1); setReload(n => n + 1); toast.success("Comentario guardado"); onChanged?.(); } catch (error) { toast.error(errorMessage(error)); } finally { setBusy(false); } };
  const moderate = async (id: number, state: string) => { try { await docs.moderate(article.id, id, state); setReload(n => n + 1); onChanged?.(); } catch (error) { toast.error(errorMessage(error)); } };
  return <section className={composerOnly ? "space-y-3" : "space-y-5 border-t pt-5"} aria-label="Comentarios">
    {!composerOnly && <div className="space-y-3"><h3 className="text-sm font-semibold">Comentarios{!loading && ` · ${total}${query.trim() ? " encontrados" : ""}`}</h3><div className="relative"><Search className="absolute left-3 top-3 size-4 text-muted-foreground"/><Input aria-label="Buscar comentarios" placeholder="Buscar por comentario, autor o fragmento…" className="pl-9" maxLength={100} value={query} onChange={e => {setQuery(e.target.value);setPage(1);}}/></div></div>}
    {article.estado !== "archivado" && <div className="space-y-2">
      {quote && <blockquote className="flex max-h-32 items-start justify-between gap-2 overflow-y-auto border-l-2 border-amber-300 bg-amber-50 p-3 text-sm text-zinc-800"><span>{quote}</span>{!composerOnly && <button onClick={onClearQuote} aria-label="Retirar cita"><X className="size-4" /></button>}</blockquote>}
      <textarea ref={composer} aria-label="Nuevo comentario" placeholder="Escribe una observación o pega una captura…" maxLength={5000} className="min-h-24 w-full rounded-lg border bg-background p-3 text-sm" value={body} onChange={e => setBody(e.target.value)} onPaste={e => { const file = Array.from(e.clipboardData.files).find(f => f.type.startsWith("image/")); if (file) { e.preventDefault(); void upload(file); } }} />
      {files.map(file => <span key={file.id} className="mr-2 inline-flex items-center gap-2 rounded border px-2 py-1 text-xs">{file.nombre}<button aria-label={`Retirar ${file.nombre}`} onClick={() => setFiles(old => old.filter(f => f.id !== file.id))}><X className="size-3" /></button></span>)}
      <div className="flex items-center justify-between"><Button variant="ghost" size="sm" disabled={busy || files.length >= 5} onClick={() => picker.current?.click()}><Paperclip className="size-4" />{busy ? "Procesando…" : "Adjuntar"}</Button><Button size="sm" disabled={busy || !body.trim()} onClick={() => void send()}><Send className="size-4" />Comentar</Button></div>
      <input ref={picker} className="hidden" type="file" accept=".png,.jpg,.jpeg,.webp,.pdf,.docx,.md,.txt" onChange={e => { if (e.target.files?.[0]) void upload(e.target.files[0]); e.target.value = ""; }} />
    </div>}
    {!composerOnly && failed && <Button variant="outline" onClick={() => setReload(n => n + 1)}>No se cargaron los comentarios. Reintentar</Button>}
    {!composerOnly && loading && <p role="status" className="text-sm text-muted-foreground">Buscando comentarios…</p>}
    {!composerOnly && !loading && !failed && !rows.length && <p className="text-sm text-muted-foreground">{query.trim() ? "No hay comentarios que coincidan con la búsqueda." : "Todavía no hay comentarios."}</p>}
    {!loading && !failed && rows.map(row => <div key={row.id} className="space-y-2 border-b pb-4">
      <div className="flex flex-wrap items-center gap-2 text-xs"><strong><SearchHighlight text={row.autor} query={query}/></strong><span className="text-muted-foreground">{dateLabel(row.creado_en)}</span>{row.estado === "resuelto" && <span className="text-green-600">Resuelto</span>}</div>
      {row.cita && <blockquote className="border-l-2 border-amber-300 pl-3 text-sm text-muted-foreground"><SearchHighlight text={row.cita} query={query}/>{row.version_articulo !== article.version && <span className="block text-xs">Cita de la versión {row.version_articulo}</span>}</blockquote>}
      {row.cita && row.version_articulo === article.version && onLocate && <button className="text-xs text-sky-600 hover:underline" onClick={() => onLocate(row)}>Ver fragmento ↗</button>}
      <p className="whitespace-pre-wrap break-words text-sm"><SearchHighlight text={row.contenido} query={query}/></p>
      {row.adjuntos.map(file => <div key={file.id} className="max-w-md">{file.mime.startsWith("image/") && <ProtectedImage src={attachmentPath(file)} alt={file.nombre} />}<button className="text-xs text-sky-600 hover:underline" onClick={() => void docs.blob(attachmentPath(file)).then(b => saveBlob(b, file.nombre)).catch(e => toast.error(errorMessage(e)))}>{file.nombre}</button></div>)}
      {(programmer || row.usuario_id === user?.id) && <div className="flex gap-3 text-xs"><button onClick={() => void moderate(row.id, row.estado === "resuelto" ? "abierto" : "resuelto")}>{row.estado === "resuelto" ? "Reabrir" : "Resolver"}</button><ConfirmActionDialog title="Retirar comentario" description="Se ocultará el comentario, conservando su constancia en Auditoría." onConfirm={() => moderate(row.id, "eliminado")} destructive><button className="text-red-600">Retirar</button></ConfirmActionDialog></div>}
    </div>)}
    {total > 20 && !failed && <div className="flex justify-between"><Button variant="ghost" disabled={page === 1 || loading} onClick={() => setPage(p => p - 1)}>Anterior</Button><span className="text-xs">Página {page}</span><Button variant="ghost" disabled={page * 20 >= total || loading} onClick={() => setPage(p => p + 1)}>Siguiente</Button></div>}
  </section>;
}
