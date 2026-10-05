import { useEffect, useMemo, useState } from "react";
import { ChevronRight, FileText, Folder, FolderOpen } from "lucide-react";
import type { Article } from "./api";
import { SearchHighlight } from "./search-highlight";

type Branch = {name: string; path: string; folders: Map<string, Branch>; articles: Article[]};
function createTree(rows: Article[]) {
  const root: Branch = {name: "", path: "", folders: new Map(), articles: []};
  for (const row of rows) {
    const folders = row.origen === "repositorio"
      ? ["Documentación del proyecto", ...(row.ruta_fuente?.split("/").slice(0,-1) ?? [])]
      : ["Artículos de la plataforma", row.categoria || "General"];
    let current = root;
    for (const name of folders) {
      if (!current.folders.has(name)) current.folders.set(name, {name, path: `${current.path}/${name}`, folders: new Map(), articles: []});
      current = current.folders.get(name)!;
    }
    current.articles.push(row);
  }
  return root;
}
function contains(branch: Branch, id: number | null): boolean {
  return branch.articles.some(row => row.id === id) || [...branch.folders.values()].some(child => contains(child,id));
}
function ArticleLink({row, selected, query, onOpen}: {row: Article; selected: number | null; query: string; onOpen: (id: number) => void}) {
  return <button type="button" aria-current={selected === row.id ? "page" : undefined} onClick={() => onOpen(row.id)} className={`mb-1 flex w-full min-w-0 items-start gap-2 rounded-lg px-2 py-2 text-left text-sm [overflow-wrap:anywhere] ${selected === row.id ? "bg-accent font-medium" : "hover:bg-muted/50"}`}><FileText className="mt-0.5 size-3.5 shrink-0 text-muted-foreground"/><span><SearchHighlight text={row.titulo} query={query}/></span></button>;
}
function FolderBranch({branch, selected, query, onOpen, depth}: {branch: Branch; selected: number | null; query: string; onOpen: (id: number) => void; depth: number}) {
  const [expanded, setExpanded] = useState(depth === 0 || contains(branch,selected));
  useEffect(() => {if (contains(branch,selected)) setExpanded(true);}, [branch, selected]);
  const open = expanded || Boolean(query.trim());
  return <div className="min-w-0">
    <button type="button" aria-expanded={open} className="flex w-full items-start gap-1.5 rounded-md py-2 text-left text-xs font-semibold hover:bg-muted/50" onClick={() => setExpanded(v => !v)}><ChevronRight className={`mt-0.5 size-3 shrink-0 transition-transform ${open ? "rotate-90" : ""}`}/>{open ? <FolderOpen className="size-4 shrink-0 text-amber-600"/> : <Folder className="size-4 shrink-0 text-amber-600"/>}<span className="min-w-0 [overflow-wrap:anywhere]">{branch.name}</span></button>
    {open && <div className="ml-2 min-w-0 border-l pl-2">{[...branch.folders.values()].sort((a,b) => a.name.localeCompare(b.name,"es",{numeric:true})).map(child => <FolderBranch key={child.path} branch={child} selected={selected} query={query} onOpen={onOpen} depth={depth+1}/>)}{branch.articles.map(row => <ArticleLink key={row.id} row={row} selected={selected} query={query} onOpen={onOpen}/>)}</div>}
  </div>;
}
export function ArticleIndex({rows, selected, query, folders, onOpen}: {rows: Article[]; selected: number | null; query: string; folders: boolean; onOpen: (id: number) => void}) {
  const tree = useMemo(() => createTree(rows), [rows]);
  return <nav aria-label="Índice de documentación" className="max-h-[65dvh] overflow-y-auto p-2">
    {folders ? [...tree.folders.values()].map(branch => <FolderBranch key={branch.path} branch={branch} selected={selected} query={query} onOpen={onOpen} depth={0}/>) : rows.map(row => <div key={row.id}><ArticleLink row={row} selected={selected} query={query} onOpen={onOpen}/><p className="mb-2 px-2 text-[10px] text-muted-foreground [overflow-wrap:anywhere]">{row.ruta_fuente || `Plataforma / ${row.categoria}`}</p></div>)}
  </nav>;
}
