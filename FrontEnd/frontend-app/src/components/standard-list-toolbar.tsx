import { Search } from "lucide-react";
import type { ReactNode } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { cn } from "@/lib/utils";

export interface QuickFilter {
  value: string;
  label: string;
  count?: number;
  className?: string;
  activeClassName?: string;
}

function filterTone(value: string) {
  if (/^(active|activo|activos|accepted|confirmed|paid|liquidado)$/.test(value)) return 'border-emerald-200 bg-emerald-50 text-emerald-800 dark:border-emerald-900 dark:bg-emerald-950/40 dark:text-emerald-200';
  if (/^(inactive|inactivo|inactivos|annulled|cancelled|rejected|errors)$/.test(value)) return 'border-rose-200 bg-rose-50 text-rose-800 dark:border-rose-900 dark:bg-rose-950/40 dark:text-rose-200';
  if (/pending|temporal|observed|draft|duplicate|future/.test(value)) return 'border-amber-200 bg-amber-50 text-amber-800 dark:border-amber-900 dark:bg-amber-950/40 dark:text-amber-200';
  return 'border-sky-200 bg-sky-50 text-sky-800 dark:border-sky-900 dark:bg-sky-950/40 dark:text-sky-200';
}

interface StandardListToolbarProps {
  search: string;
  onSearchChange: (value: string) => void;
  searchPlaceholder?: string;
  filters?: QuickFilter[];
  activeFilter?: string;
  onFilterChange?: (value: string) => void;
  /** @deprecated La descarga se presenta con ExcelDownloadButton en el encabezado. */
  resultCount: number;
  totalCount: number;
  pagination?: ReactNode;
  filterLabel?: string;
  filterControls?: ReactNode;
  resultLabel?: string;
  embedded?: boolean;
  inline?: boolean;
}

export function StandardListToolbar({
  search,
  onSearchChange,
  searchPlaceholder = "Buscar...",
  filters = [],
  activeFilter,
  onFilterChange,
  resultCount,
  totalCount,
  pagination,
  filterLabel,
  filterControls,
  resultLabel,
  embedded = false,
  inline = false,
}: StandardListToolbarProps) {
  return <div className={cn("space-y-2.5", embedded ? "" : "rounded-xl border bg-muted/20 p-3")}>
    <div className={cn(inline && "flex min-w-0 items-center gap-2 overflow-x-auto pb-0.5")}>
      <div className={cn("relative min-w-56", inline && "w-full flex-1")}>
        <Search className="absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
        <Input value={search} onChange={(event) => onSearchChange(event.target.value)} placeholder={searchPlaceholder} className="bg-background pl-9" />
      </div>
      {inline && filterControls}
    </div>
    <div className="flex flex-wrap items-center gap-1.5">
      {filterLabel && <span className="mr-1 text-[11px] font-medium text-muted-foreground">{filterLabel}</span>}
      {filters.map((filter) => <Button key={filter.value} type="button" size="sm" variant="outline" aria-pressed={activeFilter === filter.value} className={cn("h-6 rounded-full px-2 text-[11px] font-normal", filterTone(filter.value), activeFilter === filter.value ? "ring-1 ring-current ring-offset-1" : "border-transparent hover:border-current", filter.className, activeFilter === filter.value && filter.activeClassName)} onClick={() => onFilterChange?.(filter.value)}>
        {filter.label}{filter.count == null ? "" : ` (${filter.count})`}
      </Button>)}
      <span className="ml-auto text-[11px] font-normal text-muted-foreground">{resultLabel ?? `${resultCount} de ${totalCount} registro${totalCount === 1 ? "" : "s"}`}</span>
    </div>
    {!inline && filterControls}
    {pagination}
  </div>;
}
