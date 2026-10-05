import { lazy, Suspense, useEffect, useRef, useState, type RefObject } from "react";
import { createPortal } from "react-dom";
import { MessageSquare, X } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { ConfirmActionDialog } from "@/components/confirm-action-dialog";
import { Popover, PopoverAnchor, PopoverContent } from "@/components/ui/popover";
import { attachmentPath, dateLabel, docs, errorMessage, saveBlob, type Annotation, type Article, type DocComment } from "./api";
import { locateOffset, rangeFor, selectedAnchor, textIndex } from "./anchors";
import { ProtectedImage } from "./markdown";

const Comments = lazy(() => import("./comments"));
type Selection = NonNullable<ReturnType<typeof selectedAnchor>>;
type Mark = {row: Annotation; range: Range; rects: {left: number; top: number; width: number; height: number}[]};

export default function Annotations({article, body, surface, programmer, search = ""}: {article: Article; body: RefObject<HTMLDivElement | null>; surface: RefObject<HTMLDivElement | null>; programmer: boolean; search?: string}) {
  const [rows, setRows] = useState<Annotation[]>([]); const [marks, setMarks] = useState<Mark[]>([]);
  const [revision, setRevision] = useState(0); const [failed, setFailed] = useState(false);
  const [selection, setSelection] = useState<Selection | null>(null);
  const [mode, setMode] = useState<"select" | "compose" | "detail" | null>(null);
  const [active, setActive] = useState<Annotation | null>(null); const [detail, setDetail] = useState<DocComment | null>(null); const [detailError, setDetailError] = useState("");
  const [showComments, setShowComments] = useState(false); const list = useRef<HTMLDivElement>(null);
  useEffect(() => {if (search.trim()) setShowComments(true); setMode(current => current === "compose" ? current : null);}, [search]);
  const range = useRef<Range | null>(null);
  const virtual = useRef({getBoundingClientRect: () => {
    const rects = range.current?.getClientRects();
    return rects?.length ? rects[rects.length - 1] : new DOMRect();
  }});
  const changed = () => {setRevision(n => n + 1); setMode(null); setSelection(null);};
  useEffect(() => {
    let live = true; setFailed(false);
    const load = async () => {
      let cursor = 0; const all: Annotation[] = [];
      do {
        const result = await docs.annotations(article.id, cursor);
        if (!live) return;
        all.push(...result.items); cursor = result.siguiente ?? 0;
      } while (cursor);
      setRows(all);
    };
    void load().catch(() => {if (live) setFailed(true);});
    return () => {live = false;};
  }, [article.id, article.version, revision]);
  useEffect(() => {
    const root = body.current; const host = surface.current;
    if (!root || !host) return;
    let frame = 0;
    const measure = () => {
      cancelAnimationFrame(frame);
      frame = requestAnimationFrame(() => {
        const index = textIndex(root); const bounds = host.getBoundingClientRect();
        if (selection) range.current = rangeFor(root, selection.ancla, index);
        setMarks(rows.flatMap(row => {
          const anchor = locateOffset(index.text, row, article.version);
          const target = anchor && rangeFor(root, anchor, index);
          if (!target) return [];
          const rects = Array.from(target.getClientRects()).filter(r => r.width && r.height && r.right > bounds.left && r.left < bounds.right).map(r => ({
            left: Math.max(r.left, bounds.left) - bounds.left, top: r.top - bounds.top,
            width: Math.min(r.right, bounds.right) - Math.max(r.left, bounds.left), height: r.height,
          }));
          return rects.length ? [{row, range: target, rects}] : [];
        }));
      });
    };
    const observer = new ResizeObserver(measure); observer.observe(root);
    root.addEventListener("scroll", measure, true); window.addEventListener("resize", measure);
    measure();
    return () => {cancelAnimationFrame(frame); observer.disconnect(); root.removeEventListener("scroll", measure, true); window.removeEventListener("resize", measure);};
  }, [rows, article.version, body, surface, search, selection]);
  useEffect(() => {
    if (mode === "compose") return;
    let timer: ReturnType<typeof setTimeout>;
    const capture = () => {
      clearTimeout(timer);
      timer = setTimeout(() => {
        const next = body.current && selectedAnchor(body.current);
        if (next && article.estado !== "archivado") {range.current = next.range; setSelection(next); setMode("select");}
        else setMode(current => current === "select" ? null : current);
      }, 160);
    };
    document.addEventListener("selectionchange", capture);
    return () => {clearTimeout(timer); document.removeEventListener("selectionchange", capture);};
  }, [body, mode, article.estado]);
  useEffect(() => {
    if (mode !== "detail" || !active) return;
    let live = true; setDetail(null); setDetailError("");
    docs.commentDetail(article.id, active.id).then(row => {if (live) setDetail(row);}).catch(e => {if (live) setDetailError(errorMessage(e));});
    return () => {live = false;};
  }, [active, mode, article.id]);
  const reveal = (row: Annotation, scroll = false) => {
    const root = body.current; if (!root) return;
    const anchor = locateOffset(textIndex(root).text, row, article.version);
    const target = anchor && rangeFor(root, anchor);
    if (!target) {toast.info("No se puede ubicar esta cita con precisión en la versión actual."); return;}
    range.current = target; setActive(row); setSelection(null); setMode("detail");
    if (scroll) {
      const marker = surface.current?.querySelector<HTMLButtonElement>(`[data-annotation-id="${row.id}"]`);
      (marker ?? target.startContainer.parentElement)?.scrollIntoView({block: "center", behavior: "instant"});
    }
  };
  const revealRef = useRef(reveal); revealRef.current = reveal;
  useEffect(() => {
    const root = body.current; if (!root) return;
    const click = (event: MouseEvent) => {
      if (window.getSelection()?.toString() || (event.target as HTMLElement).closest("a,button") || mode === "compose") return;
      const match = marks.find(mark => Array.from(mark.range.getClientRects()).some(r => event.clientX >= r.left && event.clientX <= r.right && event.clientY >= r.top && event.clientY <= r.bottom));
      if (match) revealRef.current(match.row);
    };
    root.addEventListener("click", click);
    return () => root.removeEventListener("click", click);
  }, [body, marks, mode]);
  return <>
    {surface.current && createPortal(<div className="pointer-events-none absolute inset-0" aria-label="Anotaciones del artículo">
      {marks.map(({row, rects}) => <div key={row.id}>
        {rects.map((rect, i) => <span key={i} className={`absolute rounded-sm ${active?.id === row.id && mode === "detail" ? "bg-amber-400/40" : "bg-yellow-300/25"}`} style={rect} />)}
        <button data-annotation-id={row.id} className="pointer-events-auto absolute flex size-5 items-center justify-center rounded-full border border-amber-400 bg-amber-100 text-amber-900 shadow-sm focus-visible:outline-2" style={{left: Math.max(0, Math.min(rects[rects.length-1].left + rects[rects.length-1].width - 4, (surface.current?.clientWidth ?? 24) - 22)), top: rects[rects.length-1].top - 12}} aria-label={`Ver comentario ${row.id} sobre ${row.cita.slice(0,80)}`} title="Ver comentario del fragmento" onClick={() => reveal(row)}><MessageSquare className="size-3" /></button>
      </div>)}
    </div>, surface.current)}
    <Popover open={mode !== null} onOpenChange={open => {if (!open && mode !== "compose") setMode(null);}}>
      <PopoverAnchor virtualRef={virtual} />
      <PopoverContent side="top" align="start" collisionPadding={12} className={mode === "select" ? "w-auto p-1" : "max-h-[min(70dvh,520px)] w-[min(360px,calc(100vw-24px))] overflow-y-auto"}
        onOpenAutoFocus={e => {if (mode === "select") e.preventDefault();}}
        onCloseAutoFocus={e => e.preventDefault()} onInteractOutside={e => {if (mode === "compose") e.preventDefault();}}>
        {mode === "select" && <Button variant="ghost" size="sm" onPointerDown={e => e.preventDefault()} onClick={() => {setMode("compose"); window.getSelection()?.removeAllRanges();}}><MessageSquare className="size-4" />Comentar fragmento</Button>}
        {mode === "compose" && selection && <><div className="mb-3 flex items-center justify-between"><strong className="text-sm">Comentar fragmento</strong><ConfirmActionDialog title="Descartar comentario" description="Se cerrará el comentario que estás preparando." confirmLabel="Descartar" onConfirm={() => {setMode(null);setSelection(null);}}><Button variant="ghost" size="icon" aria-label="Cerrar comentario"><X className="size-4" /></Button></ConfirmActionDialog></div><Suspense fallback={<p>Cargando…</p>}><Comments article={article} quote={selection.cita} anchor={selection.ancla} onClearQuote={() => {}} programmer={programmer} composerOnly onChanged={changed} /></Suspense></>}
        {mode === "detail" && <><div className="mb-3 flex items-center justify-between"><strong className="text-sm">Anotación</strong><Button variant="ghost" size="icon" aria-label="Cerrar anotación" onClick={() => setMode(null)}><X className="size-4" /></Button></div>
          {detailError ? <p role="alert" className="text-sm text-destructive">{detailError}</p> : !detail ? <p className="text-sm">Cargando comentario…</p> : <div className="space-y-3 text-sm"><div><strong>{detail.autor}</strong><p className="text-xs text-muted-foreground">{dateLabel(detail.creado_en)}{detail.estado === "resuelto" ? " · Resuelto" : ""}</p></div><blockquote className="border-l-2 border-amber-300 pl-3 text-muted-foreground">{detail.cita}</blockquote><p className="whitespace-pre-wrap [overflow-wrap:anywhere]">{detail.contenido}</p>{detail.adjuntos.map(file => <div key={file.id}>{file.mime.startsWith("image/") && <ProtectedImage src={attachmentPath(file)} alt={file.nombre}/>}<button className="text-xs text-sky-600" onClick={() => void docs.blob(attachmentPath(file)).then(blob => saveBlob(blob,file.nombre)).catch(e => toast.error(errorMessage(e)))}>{file.nombre}</button></div>)}</div>}
          {marks.filter(mark => mark.row.id !== active?.id && active?.cita === mark.row.cita).map(mark => <button key={mark.row.id} className="mt-2 block text-xs text-sky-600" onClick={() => reveal(mark.row)}>Ver otra anotación de este fragmento</button>)}
        </>}
      </PopoverContent>
    </Popover>
    {failed && <Button variant="ghost" size="sm" onClick={() => setRevision(n => n + 1)}>No se cargaron las anotaciones. Reintentar</Button>}
    <div ref={list} id="doc-comments" className="mt-5 scroll-mt-24"><Button variant="ghost" size="sm" className="mb-4" onClick={() => setShowComments(v => !v)}><MessageSquare className="size-4" />{showComments ? "Ocultar comentarios" : "Comentarios y observaciones"}</Button>
      {showComments && <Suspense fallback={<p>Cargando comentarios…</p>}><Comments article={article} quote="" onClearQuote={() => {}} programmer={programmer} revision={revision} search={search} onChanged={changed} onLocate={row => reveal(row,true)} /></Suspense>}
    </div>
  </>;
}
