import { useEffect, useMemo, useRef, useState } from "react";
import { Database, Loader2, Search, X } from "lucide-react";
import { useNavigate } from "react-router-dom";

import { Input } from "@/components/ui/input";
import { Popover, PopoverAnchor, PopoverContent } from "@/components/ui/popover";
import { wolverineAPI } from "@/features/wolverine/api";
import type { GlobalSearchResult } from "@/features/wolverine/types";
import { cn } from "@/lib/utils";

export function GlobalSearch({ open, onOpenChange }: { open: boolean; onOpenChange: (open: boolean) => void }) {
  const navigate = useNavigate();
  const inputRef = useRef<HTMLInputElement>(null);
  const requestId = useRef(0);
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<GlobalSearchResult[]>([]);
  const [loading, setLoading] = useState(false);
  const [failed, setFailed] = useState(false);
  const [truncated, setTruncated] = useState(false);
  const [activeId, setActiveId] = useState<string | null>(null);
  const resultRefs = useRef(new Map<string, HTMLButtonElement>());
  const grouped = useMemo(() => Object.entries(results.reduce<Record<string, GlobalSearchResult[]>>((groups, result) => {
    (groups[result.source] ??= []).push(result);
    return groups;
  }, {})), [results]);
  const orderedResults = grouped.flatMap(([, items]) => items);
  const activeResult = orderedResults.find(item => item.id === activeId) ?? orderedResults[0];
  const onSearchKeyDown = (event: React.KeyboardEvent) => {
    if (event.key === "ArrowDown" || event.key === "ArrowUp") {
      event.preventDefault();
      if (!orderedResults.length) return;
      const index = orderedResults.findIndex(item => item.id === activeResult?.id);
      const next = orderedResults[Math.max(0, Math.min(orderedResults.length - 1, index + (event.key === "ArrowDown" ? 1 : -1)))];
      setActiveId(next.id);
      resultRefs.current.get(next.id)?.scrollIntoView({ block: "nearest" });
    } else if (event.key === "Enter" && activeResult && !loading) {
      event.preventDefault();
      select(activeResult);
    }
  };

  useEffect(() => {
    if (open) {
      const timer = window.setTimeout(() => inputRef.current?.focus(), 0);
      return () => window.clearTimeout(timer);
    }
    requestId.current += 1;
    setQuery("");
    setResults([]);
    setLoading(false);
    setFailed(false);
    setTruncated(false);
  }, [open]);

  useEffect(() => {
    const normalized = query.trim();
    if (normalized.length < 2) {
      requestId.current += 1;
      setResults([]);
      setLoading(false);
      setFailed(false);
      setTruncated(false);
      return;
    }
    const current = ++requestId.current;
    const controller = new AbortController();
    setLoading(true);
    setFailed(false);
    const timer = window.setTimeout(() => {
      void wolverineAPI.globalSearch(normalized, controller.signal).then((response) => {
        if (current === requestId.current && !controller.signal.aborted) {
          setResults(response.results);
          setTruncated(response.truncated);
        }
      }).catch(() => {
        if (current === requestId.current && !controller.signal.aborted) {
          setResults([]);
          setFailed(true);
        }
      }).finally(() => {
        if (current === requestId.current) setLoading(false);
      });
    }, 120);
    return () => { window.clearTimeout(timer); controller.abort(); };
  }, [query]);

  const select = (result: GlobalSearchResult) => {
    onOpenChange(false);
    navigate(result.url);
  };

  return <Popover open={open} onOpenChange={onOpenChange}>
    <div className={cn("mx-auto md:w-full md:max-w-xl", open ? "absolute inset-x-3 bottom-3 z-50 w-auto md:static" : "hidden md:block")}>
      <PopoverAnchor asChild>
        <div className="relative" data-global-search-anchor>
          <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            ref={inputRef}
            value={query}
            onChange={(event) => { setQuery(event.target.value); setActiveId(null); onOpenChange(true); }}
            onKeyDown={onSearchKeyDown}
            role="combobox"
            aria-expanded={open}
            aria-controls="global-search-results"
            aria-activedescendant={activeResult ? `search-${activeResult.id}` : undefined}
            onFocus={() => onOpenChange(true)}
            placeholder="Buscar menús, registros, códigos o acciones..."
            aria-label="Búsqueda global"
            clearButtonClassName="mr-10 md:mr-2"
            className="h-9 bg-background pl-9 pr-16 text-base md:bg-muted/25 md:text-sm"
          />
          {loading
            ? <Loader2 className="pointer-events-none absolute right-20 top-1/2 size-4 -translate-y-1/2 animate-spin text-muted-foreground md:right-10" />
            : !query && <kbd className="pointer-events-none absolute right-2.5 top-1/2 hidden -translate-y-1/2 rounded border bg-background/80 px-1.5 py-0.5 font-sans text-[10px] font-medium text-muted-foreground md:block">Ctrl K</kbd>}
          <button type="button" onClick={() => onOpenChange(false)} aria-label="Cerrar búsqueda global" className="absolute right-0 top-0 flex size-9 items-center justify-center rounded-md text-muted-foreground md:hidden"><X className="size-4" /></button>
        </div>
      </PopoverAnchor>
      <PopoverContent align="center" className="w-[var(--radix-popover-trigger-width)] max-w-[calc(100vw-2rem)] p-0" onOpenAutoFocus={(event) => event.preventDefault()} onCloseAutoFocus={(event) => event.preventDefault()} onInteractOutside={(event) => {
        if (event.target instanceof Element && event.target.closest("[data-global-search-anchor], [data-global-search-trigger]")) event.preventDefault();
      }}>
        <div id="global-search-results" role="listbox" className="max-h-[min(65dvh,520px,var(--radix-popover-content-available-height))] overflow-y-auto py-1" onKeyDown={onSearchKeyDown}>
          {query.trim().length < 2 && <p className="px-4 py-8 text-center text-sm text-muted-foreground">Escribe al menos 2 caracteres para buscar en menús y registros autorizados.</p>}
          {query.trim().length >= 2 && loading && results.length === 0 && <p className="px-4 py-8 text-center text-sm text-muted-foreground">Buscando coincidencias…</p>}
          {query.trim().length >= 2 && !loading && failed && <p className="px-4 py-8 text-center text-sm text-destructive">No se pudo completar la búsqueda. Intenta nuevamente.</p>}
          {query.trim().length >= 2 && !loading && !failed && results.length === 0 && <p className="px-4 py-8 text-center text-sm text-muted-foreground">No se encontraron resultados para “{query.trim()}”.</p>}
          {grouped.map(([source, items]) => <section key={source} aria-label={source}>
            <p className="px-3 pb-1 pt-2 text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">{source}</p>
            {items.map((result) => <button key={result.id} id={`search-${result.id}`} role="option" aria-selected={activeResult?.id === result.id} ref={element => { if (element) resultRefs.current.set(result.id, element); else resultRefs.current.delete(result.id); }} type="button" onMouseEnter={() => setActiveId(result.id)} onClick={() => select(result)} className={cn("flex w-full items-start gap-2 px-3 py-2.5 text-left hover:bg-accent focus-visible:bg-accent focus-visible:outline-none", activeResult?.id === result.id && "bg-accent")}>
              {result.kind === "option" ? <Search className="mt-0.5 size-4 shrink-0" /> : <Database className="mt-0.5 size-4 shrink-0" />}
              <span className="min-w-0"><span className="block truncate text-sm font-medium">{result.title}</span><span className="block truncate text-xs text-muted-foreground">{result.subtitle}</span></span>
            </button>)}
          </section>)}
          {!loading && truncated && <p className="border-t px-4 py-2 text-center text-xs text-muted-foreground">Hay más coincidencias. Afina el criterio para reducir los resultados.</p>}
        </div>
      </PopoverContent>
    </div>
  </Popover>;
}
