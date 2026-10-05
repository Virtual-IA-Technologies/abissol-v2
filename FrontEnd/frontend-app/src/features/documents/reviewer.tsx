import { useEffect, useRef, useState, type PointerEvent } from "react";
import { ChevronLeft, ChevronRight, Highlighter, Maximize2, MessageSquarePlus, Minimize2, MousePointer2, Save, Trash2, ZoomIn, ZoomOut } from "lucide-react";
import { toast } from "sonner";
import type { PDFDocumentProxy } from "pdfjs-dist";
import { PdfPage } from './pdf-page';
import { PdfTextTools } from './pdf-text-tools';
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { documentAnnotationAPI, type Annotation } from "./notes-api";


type Props = { fileId?: number; number?: number; localNotes?: Annotation[]; onLocalNotes?: (items: Annotation[]) => void; url: string; name: string; isPdf: boolean; onDirtyChange?: (dirty: boolean) => void };
type Point = { x: number; y: number };

export default function DocumentReviewer({ fileId, number = 1, localNotes = [], onLocalNotes, url, name, isPdf, onDirtyChange }: Props) {
  const root = useRef<HTMLDivElement>(null);
  const viewport = useRef<HTMLDivElement>(null);
  const [pdf, setPdf] = useState<PDFDocumentProxy | null>(null);
  const [page, setPage] = useState(1);
  const [zoom, setZoom] = useState(1);
  const [width, setWidth] = useState(800);
  const [items, setItems] = useState<Annotation[]>([]);
  const savedItems = useRef<Annotation[]>([]);
  const [revision, setRevision] = useState(0);
  const [editable, setEditable] = useState(false);
  const [dirty, setDirty] = useState(false);
  const [busy, setBusy] = useState(false);
  const [rendering, setRendering] = useState(true);
  const [error, setError] = useState("");
  const [full, setFull] = useState(false);
  const [tool, setTool] = useState<"view" | "highlight" | "comment">("view");
  const drawingPage = useRef(1);
  const [start, setStart] = useState<Point | null>(null);
  const [draft, setDraft] = useState<Annotation | null>(null);
  const [note, setNote] = useState("");
  const [comments, setComments] = useState(false);
  const [selected, setSelected] = useState<string | null>(null);
  const pendingChanges = dirty || draft?.kind === "comment";

  useEffect(() => {
    let cancelled = false;
    if (!fileId) { savedItems.current = localNotes; setItems(localNotes); setEditable(!!onLocalNotes); return; }
    void documentAnnotationAPI.get(fileId, number).then(state => {
      if (cancelled) return;
      savedItems.current = state.items; setItems(state.items); setRevision(state.revision); setEditable(state.can_edit);
    }).catch(() => { if (!cancelled) toast.error("No se pudieron cargar las anotaciones. Vuelve a abrir el visor."); });

    return () => { cancelled = true; };
  // Local marks are initialized once; the parent remounts when the file changes.
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [fileId, number]);

  useEffect(() => {
    onDirtyChange?.(pendingChanges);
    const warn = (event: BeforeUnloadEvent) => { if (pendingChanges) { event.preventDefault(); event.returnValue = ""; } };
    window.addEventListener("beforeunload", warn);
    return () => window.removeEventListener("beforeunload", warn);
  }, [pendingChanges, onDirtyChange]);

  useEffect(() => {
    const host = viewport.current;
    if (!host) return;
    const observer = new ResizeObserver(entries => setWidth(Math.max(200, entries[0].contentRect.width - 32)));
    observer.observe(host);
    const change = () => setFull(document.fullscreenElement === root.current);
    document.addEventListener("fullscreenchange", change);
    return () => { observer.disconnect(); document.removeEventListener("fullscreenchange", change); };
  }, []);

  useEffect(() => {
    if (!isPdf) return;
    let cancelled = false;
    let task: { destroy: () => Promise<void> } | undefined;
    void (async () => {
      const engine = await import("pdfjs-dist");
      const worker = await import("pdfjs-dist/build/pdf.worker.min.mjs?url");
      if (cancelled) return;
      engine.GlobalWorkerOptions.workerSrc = worker.default;
      const loading = engine.getDocument({ url, enableXfa: false });
      task = loading;
      const document = await loading.promise;
      if (!cancelled) setPdf(document);
    })().catch(() => { if (!cancelled) setError("No se pudo leer este PDF. Puede estar protegido con contraseña o dañado."); });
    return () => { cancelled = true; void task?.destroy(); };
  }, [url, isPdf]);

  const changeItems = (next: Annotation[]) => { setItems(next); setDirty(true); };
  const point = (event: PointerEvent<HTMLDivElement>): Point => {
    const rect = event.currentTarget.getBoundingClientRect();
    return { x: Math.max(0, Math.min(.999, (event.clientX - rect.left) / rect.width)), y: Math.max(0, Math.min(.999, (event.clientY - rect.top) / rect.height)) };
  };
  const rectangle = (a: Point, b: Point): Annotation => ({ id: crypto.randomUUID(), page: drawingPage.current, kind: "highlight", x: Math.min(a.x, b.x), y: Math.min(a.y, b.y), width: Math.max(.001, Math.abs(a.x - b.x)), height: Math.max(.001, Math.abs(a.y - b.y)), text: "" });
  const down = (event: PointerEvent<HTMLDivElement>, pageNumber: number, ready: boolean) => {
    if (!editable || busy || !ready || items.length >= 500 || tool === "view" || event.button !== 0) return;
    drawingPage.current = pageNumber;
    setPage(pageNumber);
    event.currentTarget.setPointerCapture(event.pointerId);
    const p = point(event);
    if (tool === "comment") {
      setDraft({ id: crypto.randomUUID(), page: pageNumber, kind: "comment", ...p, width: .001, height: .001, text: "" });
      setNote(""); setComments(true);
    } else { setStart(p); setDraft(null); }
  };
  const save = async () => {
    setBusy(true);
    try {
      const state = fileId ? await documentAnnotationAPI.save(fileId, number, revision, items) : { items, revision: 0 };
      if (!fileId) onLocalNotes?.(items);
      savedItems.current = state.items; setRevision(state.revision); setDirty(false); toast.success(fileId ? "Anotaciones guardadas" : "Notas listas para subir");
    } catch (caught: unknown) {
      const failure = caught as { response?: { data?: { detail?: string } } };
      toast.error(failure.response?.data?.detail || "No se pudieron guardar las anotaciones");
    } finally { setBusy(false); }
  };
  const maximize = async () => {
    try { if (document.fullscreenElement) await document.exitFullscreen(); else await root.current?.requestFullscreen(); }
    catch { toast.error("Este navegador no permite pantalla completa aquí"); }
  };

  const jump = (next: number) => {
    const target = Math.max(1, Math.min(pdf?.numPages || 1, next));
    setPage(target);
    viewport.current?.querySelector(`[data-pdf-page="${target}"]`)?.scrollIntoView({block: 'start'});
  };
  const overlay = (pageNumber: number, ready: boolean) => (
<div className="absolute inset-0" style={{ cursor: tool === "view" ? "default" : "crosshair", touchAction: tool === "view" ? "auto" : "none" }} onPointerDown={event => down(event, pageNumber, ready)}
            onPointerMove={event => { if (start) setDraft(rectangle(start, point(event))); }}
            onPointerCancel={() => { setStart(null); setDraft(null); }}
            onPointerUp={event => { if (start) { const mark = rectangle(start, point(event)); if (mark.width > .003 && mark.height > .003) changeItems([...items, mark]); setStart(null); setDraft(null); } }}>
            {[...items, ...(draft?.kind === "highlight" ? [draft] : [])].filter(a => a.page === pageNumber).map(a => <button key={a.id} title={a.text || "Resaltado"} aria-label={a.text || "Resaltado"} type="button"
              onPointerDown={event => { if (tool === "view") event.stopPropagation(); }}
              onClick={() => { setSelected(a.id); setComments(true); }}
              className={a.kind === "highlight" ? "absolute border border-yellow-500/60 bg-yellow-300/40" : "absolute -translate-x-1/2 -translate-y-1/2 rounded-full bg-blue-600 p-1 text-white"}
              style={{ left: `${a.x * 100}%`, top: `${a.y * 100}%`, ...(a.kind === "highlight" ? { width: `${a.width * 100}%`, height: `${a.height * 100}%` } : {}) }}>
              {a.kind === "comment" && <MessageSquarePlus size={16} />}
            </button>)}
          </div>
  );
  return <div ref={root} tabIndex={0} onKeyDown={event=>{if((event.ctrlKey||event.metaKey)&&event.key.toLowerCase()==='f'){event.preventDefault();root.current?.querySelector<HTMLInputElement>('[aria-label="Buscar texto dentro del PDF"]')?.focus();return;}if((event.target as HTMLElement).closest('input,textarea,[contenteditable=true],[role=menu],[role=combobox]'))return;if(event.key==='Delete'&&selected&&editable&&!busy){event.preventDefault();changeItems(items.filter(item=>item.id!==selected));setSelected(null);}}} className="flex h-full min-h-0 flex-col bg-background outline-none">
    <div className="flex flex-wrap items-center gap-1 border-b p-2">
      {isPdf && <><Button size="icon" variant="ghost" title="Página anterior" disabled={page === 1} onClick={() => jump(page - 1)}><ChevronLeft /></Button><span className="text-xs">{page} / {pdf?.numPages || "…"}</span><Button size="icon" variant="ghost" title="Página siguiente" disabled={!pdf || page >= pdf.numPages} onClick={() => jump(page + 1)}><ChevronRight /></Button></>}
      <Button size="icon" variant="ghost" title="Reducir" onClick={() => setZoom(z => Math.max(.25, z - .25))}><ZoomOut /></Button>
      <Button size="sm" variant="ghost" onClick={() => setZoom(1)} title="Ajustar al ancho">{Math.round(zoom * 100)}%</Button>
      <Button size="icon" variant="ghost" title="Ampliar" onClick={() => setZoom(z => Math.min(3, z + .25))}><ZoomIn /></Button>
      <Button size="icon" variant={tool === "view" ? "secondary" : "ghost"} title="Consultar" onClick={() => { setTool("view"); setDraft(null); }}><MousePointer2 /></Button>
      <Button size="sm" variant={tool === "highlight" ? "secondary" : "ghost"} disabled={!editable || busy} onClick={() => { setTool("highlight"); setDraft(null); }}><Highlighter />Resaltar</Button>
      <Button size="sm" variant={tool === "comment" ? "secondary" : "ghost"} disabled={!editable || busy} onClick={() => { setTool("comment"); setComments(true); }}><MessageSquarePlus />Comentar</Button>
      <Button size="sm" variant="ghost" onClick={() => setComments(v => !v)}>Notas ({items.length})</Button>
      <div className="flex-1" />
      {editable && pendingChanges && <Button size="sm" variant="ghost" disabled={busy} onClick={() => { setItems(savedItems.current); setDirty(false); setDraft(null); setStart(null); }}>Descartar cambios</Button>}
      {editable && <Button size="sm" disabled={!dirty || busy || draft?.kind === "comment"} onClick={() => void save()}><Save />{busy ? "Guardando…" : dirty ? "Guardar notas *" : "Notas guardadas"}</Button>}
      <Button size="icon" variant="ghost" title={full ? "Restaurar" : "Pantalla completa"} onClick={() => void maximize()}>{full ? <Minimize2 /> : <Maximize2 />}</Button>
    </div>
    <div className="border-b px-3 py-1 text-xs text-muted-foreground">{tool === "highlight" ? "Arrastra sobre la zona que quieres resaltar. " : tool === "comment" ? "Pulsa un punto de la página y escribe tu comentario. " : ""}{fileId ? "Las notas se guardan en ABISSOL; el archivo original se conserva." : "Vista previa local. Guarda las notas antes de subir el archivo."}</div>
    <PdfTextTools key={url} pdf={pdf} url={url} name={name} isPdf={isPdf} jump={jump}/>
    <div className="flex min-h-0 flex-1">
      <div ref={viewport} className="min-w-0 flex-1 overflow-auto bg-muted/40 p-4">
        {error ? <p role="alert" className="p-4 text-destructive">{error}</p> : isPdf ? pdf ? Array.from({length:pdf.numPages},(_,index)=><PdfPage key={index+1} pdf={pdf} page={index+1} width={width} zoom={zoom} viewport={viewport} onVisible={setPage} overlay={overlay}/>) : <p role="status">Cargando PDF…</p> : <div className="relative mx-auto bg-white shadow" style={{width:width*zoom}}>
          <img src={url} alt={name} className="block h-auto w-full" onLoad={()=>setRendering(false)} onError={()=>setError('El navegador no admite esta imagen')}/>
          {overlay(1,!rendering)}
        </div>}

      </div>
      {comments && <aside className="w-64 max-w-[45%] shrink-0 space-y-3 overflow-y-auto border-l p-3 text-sm">
        {draft?.kind === "comment" && <div className="space-y-2"><label htmlFor="document-note">Comentario</label><Input id="document-note" autoFocus maxLength={2000} value={note} onChange={event => setNote(event.target.value)} /><Button size="sm" disabled={!note.trim() || busy} onClick={() => { changeItems([...items, { ...draft, text: note.trim() }]); setDraft(null); setNote(""); }}>Agregar</Button><Button size="sm" variant="ghost" onClick={() => setDraft(null)}>Cancelar</Button></div>}
        {items.map(a => <div key={a.id} className={`rounded border p-2 ${selected === a.id ? "border-primary" : ""}`}><button className="text-left text-xs text-muted-foreground" onClick={() => { jump(a.page); setSelected(a.id); }}>Página {a.page} · {a.kind === "highlight" ? "Resaltado" : "Comentario"}</button><p className="whitespace-pre-wrap break-words">{a.text}</p>{editable && <Button title="Quitar anotación" size="icon" variant="ghost" disabled={busy} onClick={() => changeItems(items.filter(item => item.id !== a.id))}><Trash2 size={14} /></Button>}</div>)}
        {!items.length && !draft && <p className="text-muted-foreground">Sin anotaciones.</p>}
      </aside>}
    </div>
  </div>;
}
