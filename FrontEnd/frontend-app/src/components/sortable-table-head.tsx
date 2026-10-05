import { ArrowDown, ArrowUp, ArrowUpDown } from "lucide-react";

import { Button } from "@/components/ui/button";
import { TableHead } from "@/components/ui/table";
import { cn } from "@/lib/utils";
import type { SortDirection } from "@/lib/table-tools";

interface SortableTableHeadProps {
  label: string;
  active: boolean;
  direction: SortDirection;
  onSort: () => void;
  className?: string;
}

export function SortableTableHead({ label, active, direction, onSort, className }: SortableTableHeadProps) {
  const Icon = !active ? ArrowUpDown : direction === "asc" ? ArrowUp : ArrowDown;
  return <TableHead className={cn("px-1", className)}>
    <Button type="button" variant="ghost" size="sm" className="h-8 gap-1 px-2 font-medium" onClick={onSort} aria-label={`Ordenar por ${label}`}>
      {label}<Icon className="size-3.5 text-muted-foreground" />
    </Button>
  </TableHead>;
}
