import { ChevronLeft, ChevronRight, ChevronsLeft, ChevronsRight } from "lucide-react";

import { SearchableSelect } from "@/components/searchable-select";
import { Button } from "@/components/ui/button";
import type { PageSize } from "@/lib/use-list-pagination";
import { cn } from "@/lib/utils";

interface ListPaginationProps {
  page: number;
  pageSize: PageSize;
  totalItems: number;
  totalPages: number;
  onPageChange: (page: number) => void;
  onPageSizeChange: (pageSize: PageSize) => void;
  embedded?: boolean;
  compactWhenSinglePage?: boolean;
  includeAll?: boolean;
}

export function ListPagination({ page, pageSize, totalItems, totalPages, onPageChange, onPageSizeChange, embedded = false, compactWhenSinglePage = false, includeAll = true }: ListPaginationProps) {
  const start = totalItems === 0 ? 0 : pageSize === "all" ? 1 : (page - 1) * pageSize + 1;
  const end = pageSize === "all" ? totalItems : Math.min(page * pageSize, totalItems);
  const navigationDisabled = totalItems === 0 || pageSize === "all";
  const singlePage = totalPages <= 1;

  return <div className={cn("flex flex-wrap items-center gap-3 text-sm", embedded ? "border-t pt-2.5" : "rounded-xl border bg-muted/20 px-3 py-2", compactWhenSinglePage && singlePage ? "justify-start" : "justify-between")}>
    <div className="flex items-center gap-2">
      <span className="text-muted-foreground">Filas por página</span>
      <SearchableSelect aria-label="Filas por página" className="h-8 w-24" value={String(pageSize)} onValueChange={(value) => onPageSizeChange(value === "all" ? "all" : Number(value) as PageSize)} options={[{ value: "10", label: "10" }, { value: "25", label: "25" }, { value: "50", label: "50" }, ...(includeAll ? [{ value: "all", label: "Todos" }] : [])]} searchPlaceholder="Buscar tamaño..." />
    </div>
    {!(compactWhenSinglePage && singlePage) && <><span className="text-muted-foreground">{start}-{end} de {totalItems}</span>
    <div className="flex items-center gap-1">
      <Button type="button" variant="outline" size="icon" className="size-8" aria-label="Primera página" title="Primera página" disabled={navigationDisabled || page <= 1} onClick={() => onPageChange(1)}><ChevronsLeft className="size-4" /></Button>
      <Button type="button" variant="outline" size="icon" className="size-8" aria-label="Página anterior" title="Página anterior" disabled={navigationDisabled || page <= 1} onClick={() => onPageChange(page - 1)}><ChevronLeft className="size-4" /></Button>
      <span className="min-w-24 text-center">Página {totalItems === 0 ? 0 : page} de {totalItems === 0 ? 0 : totalPages}</span>
      <Button type="button" variant="outline" size="icon" className="size-8" aria-label="Página siguiente" title="Página siguiente" disabled={navigationDisabled || page >= totalPages} onClick={() => onPageChange(page + 1)}><ChevronRight className="size-4" /></Button>
      <Button type="button" variant="outline" size="icon" className="size-8" aria-label="Última página" title="Última página" disabled={navigationDisabled || page >= totalPages} onClick={() => onPageChange(totalPages)}><ChevronsRight className="size-4" /></Button>
    </div></>}
  </div>;
}
