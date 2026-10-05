import { lazy, Suspense, useEffect, useRef, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { ArrowLeft, BookOpen, EllipsisVertical, Plus, Search, Upload } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ActionButton } from "@/components/action-button";
import { ExcelDownloadButton } from "@/components/excel-download-button";
import { SearchableSelect } from "@/components/searchable-select";
import { ConfirmActionDialog } from "@/components/confirm-action-dialog";
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuSeparator, DropdownMenuTrigger } from "@/components/ui/dropdown-menu";
import { useAuth } from "@/context/AuthContext";
import { usePlatformSettings } from "@/context/PlatformSettingsContext";
import { downloadExcelXlsx } from "@/lib/table-tools";
import { attachmentPath, dateLabel, docs, errorMessage, saveBlob, type Article, type Index } from "./api";
import { Markdown } from "./markdown";
import { SearchHighlight } from "./search-highlight";
import { ArticleIndex } from "./article-index";
import "./documentation.css";
const EditSheet = lazy(() => import("./edit-sheet"));
const Annotations = lazy(() => import("./annotations"));
const History = lazy(() => import("./history"));
const audiences = [{value:"",label:"Todas las audiencias"},{value:"general",label:"Manuales de uso"},{value:"tecnica",label:"Documentación técnica"},{value:"interna",label:"Memoria interna"}];

export default function DocumentationPage() {
  const {user, impersonation} = useAuth(); const {settings} = usePlatformSettings();
  const programmer = Boolean(user?.roles.some(r => r.es_superusuario && r.is_active)) && !impersonation?.active;
  const [params, setParams] = useSearchParams(); const selected = Number(params.get("articulo")) || null;
  const [query, setQuery] = useState(params.get("buscar") || ""); const [category, setCategory] = useState(""); const [audience, setAudience] = useState(""); const [state, setState] = useState(""); const [order, setOrder] = useState("titulo"); const [page, setPage] = useState(1); const [size, setSize] = useState(10);
  const [index, setIndex] = useState<Index>({items:[], total:0, categorias:[], puede_editar:false});
  const [view, setView] = useState("carpetas");
  const urlQuery = params.get("buscar") || "";
  useEffect(() => {setQuery(urlQuery);setPage(1);}, [urlQuery]);
  const [article, setArticle] = useState<Article | null>(null); const [loading, setLoading] = useState(true); const [articleLoading, setArticleLoading] = useState(false); const [error, setError] = useState(""); const [articleError, setArticleError] = useState(""); const [reload, setReload] = useState(0); const [busy, setBusy] = useState(false);
  const [editing, setEditing] = useState(false); const [editArticle, setEditArticle] = useState<Article | null>(null); const [history, setHistory] = useState(false);
  const importPicker = useRef<HTMLInputElement>(null); const attachmentPicker = useRef<HTMLInputElement>(null); const body = useRef<HTMLDivElement>(null); const surface = useRef<HTMLDivElement>(null);
  const filters = {q:query, categoria:category, audiencia:audience, estado:state, orden:order};
  useEffect(() => {
    let live = true; setLoading(true); setError("");
    const timer = setTimeout(() => docs.index({q:query,categoria:category,audiencia:audience,estado:state,orden:order,pagina:page,tamano:view === "carpetas" ? 0 : size}).then(r => {if (live) setIndex(r);}).catch(e => {if (live) setError(errorMessage(e));}).finally(() => {if (live) setLoading(false);}), 180);
    return () => {live = false; clearTimeout(timer);};
  }, [query, category, audience, state, order, page, size, reload, view]);
  useEffect(() => {
    let live = true; setArticle(null); setArticleError(""); setHistory(false);
    if (!selected) return;
    setArticleLoading(true); docs.article(selected).then(r => {if (live) setArticle(r);}).catch(e => {if (live) setArticleError(errorMessage(e));}).finally(() => {if (live) setArticleLoading(false);});
    return () => {live = false;};
  }, [selected, reload]);
  const open = (id: number | null) => {const next = new URLSearchParams(params); if (id) next.set("articulo",String(id)); else next.delete("articulo"); setParams(next);};
  const run = async (action: () => Promise<unknown>) => { if (busy) return; setBusy(true); try {await action();} catch(e) {toast.error(errorMessage(e));} finally {setBusy(false);} };
  const saved = (row: Article) => { setEditing(false); setHistory(false); open(row.id); setReload(n => n + 1); };
  const importFile = async (file: File) => run(async () => {
    if (file.size > 8 * 1024 * 1024) {toast.error("El máximo es 8 MB"); return;}
    const markdown = /\.(md|txt)$/i.test(file.name);
    let content = `# ${file.name}\n\nConsulta el archivo adjunto.`;
    if (markdown) {
      try { content = new TextDecoder("utf-8", {fatal:true}).decode(await file.arrayBuffer()); }
      catch { toast.error("El archivo de texto debe estar guardado en UTF-8."); return; }
    }
    if (content.length > 200000) {toast.error("El artículo admite hasta 200 000 caracteres."); return;}
    const row = await docs.create({titulo:file.name.replace(/\.[^.]+$/, "").slice(0,180),resumen:"Documento importado",categoria:"Importados",audiencia:"interna",estado:"borrador",contenido:content,motivo:`Importación de ${file.name}`.slice(0,500)});
    try { if (!markdown) await docs.upload(row.id,file,"articulo"); } finally { saved(row); }
    toast.success("Importado como borrador interno. Revísalo antes de publicar.");
  });
  const excel = () => run(async () => {const result = await docs.index({...filters,tamano:0}); await downloadExcelXlsx("documentacion", result.items, [{header:"Título",value:r=>r.titulo},{header:"Categoría",value:r=>r.categoria},{header:"Audiencia",value:r=>r.audiencia},{header:"Estado",value:r=>r.estado},{header:"Versión",value:r=>r.version},{header:"Revisado",value:r=>dateLabel(r.actualizado_en)}], {organizationName:settings.organization_name,criteria:{Búsqueda:query,Categoría:category,Audiencia:audience,Estado:state,Orden:order,Artículos:result.total}});});
  const sections = (article?.contenido || "").split("\n").flatMap((line,i) => /^#{1,3}\s/.test(line) ? [{id:`seccion-${i+1}`,label:line.replace(/^#+\s*/,"")}] : []);
  return <div className="min-w-0 space-y-5 p-4 lg:p-6">
    <div className="flex flex-wrap items-center justify-between gap-3"><div><h1 className="text-xl font-semibold">Documentación</h1><p className="text-sm text-muted-foreground">Guías, conocimientos y respuestas para trabajar mejor.</p></div><div className="flex items-center gap-2">
      {programmer && <ActionButton tone="new" onClick={() => {setEditArticle(null);setEditing(true);}}><Plus className="size-4" />Nuevo</ActionButton>}
      <ExcelDownloadButton onDownload={excel} disabled={busy} />
      <DropdownMenu><DropdownMenuTrigger asChild><Button variant="outline" size="icon" aria-label="Opciones de documentación" disabled={busy}><EllipsisVertical className="size-4" /></Button></DropdownMenuTrigger><DropdownMenuContent align="end">
        <DropdownMenuItem onSelect={() => void run(async () => saveBlob(await docs.bundle(filters),"documentacion.zip"))}>Descargar artículos filtrados · ZIP</DropdownMenuItem>
        {programmer && <><DropdownMenuSeparator /><DropdownMenuItem onSelect={() => importPicker.current?.click()}>Importar archivo</DropdownMenuItem><DropdownMenuItem onSelect={() => void run(async () => {const result = await docs.sync();setReload(n=>n+1);toast.success(`${result.actualizados} artículos actualizados`);})}>Actualizar documentación del proyecto</DropdownMenuItem></>}
      </DropdownMenuContent></DropdownMenu>
    </div></div>
    <input ref={importPicker} type="file" className="hidden" accept=".md,.txt,.pdf,.docx,.png,.jpg,.jpeg,.webp" onChange={e => {if(e.target.files?.[0]) void importFile(e.target.files[0]);e.target.value="";}} />
    <div className="min-w-0 overflow-hidden rounded-xl border bg-card">
      <div className="space-y-3 border-b p-4">
        <div className="doc-filters"><div className="relative min-w-0"><Search className="absolute left-3 top-3 size-4 text-muted-foreground" /><Input aria-label="Buscar documentación y comentarios" className="h-10 pl-9" placeholder="Buscar artículos y comentarios…" maxLength={100} value={query} onChange={e => {setQuery(e.target.value);setPage(1);}} /></div>
          <SearchableSelect aria-label="Categoría" value={category} onValueChange={v=>{setCategory(v);setPage(1);}} options={[{value:"",label:"Todas las categorías"},...index.categorias.map(value=>({value,label:value}))]} />
          {programmer && <><SearchableSelect aria-label="Filtrar audiencia" value={audience} onValueChange={v=>{setAudience(v);setPage(1);}} options={audiences} /><SearchableSelect aria-label="Filtrar estado" value={state} onValueChange={v=>{setState(v);setPage(1);}} options={[{value:"",label:"Todos los estados"},...['borrador','publicado','archivado'].map(value=>({value,label:value}))]} /></>}
          <SearchableSelect aria-label="Orden de artículos" value={order} onValueChange={v=>{setOrder(v);setPage(1);}} options={[{value:"titulo",label:"Título A–Z"},{value:"fecha",label:"Más recientes"}]} />
        </div>
        <div className="flex flex-wrap items-center justify-between gap-3">
          <span className="text-xs text-muted-foreground">{index.total} artículos</span>
          <div className="flex flex-wrap items-center gap-2"><div className="w-36"><SearchableSelect aria-label="Vista del índice" value={view} onValueChange={v => {setView(v);setPage(1);}} options={[{value:"carpetas",label:"Carpetas"},{value:"todos",label:"Todos"}]}/></div>{view === "todos" && <div className="flex items-center gap-1"><Button size="sm" variant="ghost" aria-label="Página anterior" disabled={page===1||loading} onClick={()=>setPage(p=>p-1)}>‹</Button><span className="whitespace-nowrap px-1 text-xs">{page} / {size ? Math.max(1,Math.ceil(index.total/size)) : 1}</span><Button size="sm" variant="ghost" aria-label="Página siguiente" disabled={!size||page*size>=index.total||loading} onClick={()=>setPage(p=>p+1)}>›</Button><div className="ml-2 w-24 min-w-0"><SearchableSelect aria-label="Artículos por página" value={String(size)} onValueChange={v=>{setSize(Number(v));setPage(1);}} options={[10,25,50,0].map(n=>({value:String(n),label:n ? String(n):"Todos"}))} /></div></div>}</div>
        </div>
      </div>
      <div className="grid min-w-0 lg:grid-cols-[260px_minmax(0,1fr)] xl:grid-cols-[280px_minmax(0,1fr)]">
      <aside className={`${selected ? "hidden lg:block" : "block"} min-w-0 lg:border-r`}>
        <h2 className="border-b px-4 py-3 text-sm font-medium">Índice</h2>
        {loading ? <p className="p-4 text-sm text-muted-foreground">Buscando…</p> : error ? <p role="alert" className="p-4 text-sm text-destructive">{error}</p> : !index.items.length ? <p className="p-4 text-sm text-muted-foreground">No hay artículos para estos filtros.</p> : <ArticleIndex rows={index.items} selected={selected} query={query} folders={view === "carpetas"} onOpen={open}/>}
      </aside>
      <section className={`${selected ? "block" : "hidden lg:block"} min-w-0 p-4 md:p-7`}>
        <Button variant="ghost" size="sm" className="mb-3 lg:hidden" onClick={()=>open(null)}><ArrowLeft className="size-4" />Índice</Button>
        {articleLoading ? <p>Cargando artículo…</p> : articleError ? <p role="alert" className="text-destructive">{articleError}</p> : !article ? <div className="flex min-h-80 flex-col items-center justify-center gap-3 text-muted-foreground"><BookOpen className="size-9" /><p>Elige un artículo del índice para comenzar.</p></div> : <>
          <div className="mb-6 flex items-start justify-between gap-4"><div className="min-w-0 [overflow-wrap:anywhere]"><p className="mb-2 text-xs text-muted-foreground">{article.categoria} · v{article.version}</p><h2 className="text-2xl font-semibold"><SearchHighlight text={article.titulo} query={query}/></h2><p className="mt-2 text-sm text-muted-foreground"><SearchHighlight text={article.resumen} query={query}/></p><p className="mt-2 text-xs text-muted-foreground">Revisado: {dateLabel(article.actualizado_en)}</p></div><DropdownMenu><DropdownMenuTrigger asChild><Button className="shrink-0" variant="ghost" size="icon" aria-label="Opciones del artículo" disabled={busy}><EllipsisVertical className="size-4" /></Button></DropdownMenuTrigger><DropdownMenuContent align="end">
            <DropdownMenuItem onSelect={()=>void run(async()=>saveBlob(await docs.blob(`/documentacion/${article.id}/exportar`),`documento-${article.id}.md`))}>Descargar Markdown</DropdownMenuItem>
            <DropdownMenuItem onSelect={()=>void run(async()=>{if(body.current) await (await import("./exports")).exportHtml(body.current,article);})}>Descargar HTML</DropdownMenuItem>
            <DropdownMenuItem onSelect={()=>void run(async()=>{if(body.current) await (await import("./exports")).exportHtml(body.current,article,true);})}>Imprimir / guardar PDF</DropdownMenuItem>
            {programmer && <><DropdownMenuSeparator /><DropdownMenuItem onSelect={() => {
              if (article.origen === "repositorio") void run(async () => { const row = await docs.propose(article.id); open(row.id); setEditArticle(row); setEditing(true); });
              else { setEditArticle(article); setEditing(true); }
            }}>{article.origen === "repositorio" ? "Proponer edición" : "Editar"}</DropdownMenuItem><DropdownMenuItem onSelect={()=>setHistory(true)}>Historial de cambios</DropdownMenuItem>{article.origen!=="repositorio"&&<DropdownMenuItem onSelect={()=>attachmentPicker.current?.click()}>Adjuntar archivo</DropdownMenuItem>}</>}
          </DropdownMenuContent></DropdownMenu></div>
          <input ref={attachmentPicker} type="file" className="hidden" accept=".md,.txt,.pdf,.docx,.png,.jpg,.jpeg,.webp" onChange={e=>{const file=e.target.files?.[0];if(file)void run(async()=>{await docs.upload(article.id,file,"articulo");setReload(n=>n+1);});e.target.value="";}} />
          {sections.length>1&&<details className="mb-6 rounded-lg border px-3 py-2 text-sm"><summary className="cursor-pointer text-muted-foreground">En este artículo</summary><nav className="mt-2 space-y-1">{sections.map(s=><a key={s.id} href={`#${s.id}`} className="block text-sky-600">{s.label}</a>)}</nav></details>}
          {query.trim() && <a href="#doc-comments" className="mb-4 inline-block text-sm text-sky-600 hover:underline">Buscar coincidencias en comentarios ↓</a>}
          <div ref={surface} className="relative"><div ref={body} className="doc-prose"><Markdown content={article.contenido||""} articleId={article.id} search={query}/></div></div>
          {!!article.adjuntos?.length&&<div className="mt-6 border-t pt-4"><h3 className="mb-2 text-sm font-medium">Archivos adjuntos</h3>{article.adjuntos.map(file=><button key={file.id} className="mr-4 mb-2 inline-flex items-center gap-2 text-sm text-sky-600 hover:underline" onClick={()=>void run(async()=>saveBlob(await docs.blob(attachmentPath(file)),file.nombre))}><Upload className="size-3" />{file.nombre} <span className="text-xs text-muted-foreground">{Math.ceil(file.tamano/1024)} KB</span></button>)}</div>}
          <Suspense fallback={<p className="mt-5 text-sm text-muted-foreground">Cargando anotaciones…</p>}><Annotations key={`${article.id}-${article.version}`} article={article} body={body} surface={surface} programmer={programmer} search={query}/></Suspense>
          {programmer&&article.origen!=="repositorio"&&article.estado!=="archivado"&&<div className="mt-5"><ConfirmActionDialog title="Archivar artículo" description="Dejará de estar disponible para lectores. Se conservarán el contenido y el historial." confirmLabel="Archivar" destructive onConfirm={()=>run(async()=>{await docs.archive(article.id,article.version);setReload(n=>n+1);})}><button className="text-xs text-muted-foreground hover:text-red-600">Archivar</button></ConfirmActionDialog></div>}
        </>}
      </section>
      </div>
    </div>
    {editing&&<Suspense fallback={<p>Cargando formulario…</p>}><EditSheet key={editArticle?.id||"nuevo"} article={editArticle} onClose={()=>setEditing(false)} onSaved={saved}/></Suspense>}
    {history&&article&&<Suspense fallback={<p>Cargando historial…</p>}><History article={article} onClose={()=>setHistory(false)} onRestored={saved}/></Suspense>}
  </div>;
}
