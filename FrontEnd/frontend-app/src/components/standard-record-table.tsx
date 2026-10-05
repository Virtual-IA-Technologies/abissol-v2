import type { ReactNode } from "react";

import { RecordContextMenu } from "@/components/record-context-menu";
import { RowActionsMenu, type DoubleClickChoice, type RowAction } from "@/components/row-actions-menu";
import { SortableTableHead } from "@/components/sortable-table-head";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import type { SortDirection } from "@/lib/table-tools";
import { cn } from "@/lib/utils";

export type StandardRecordColumn<T> = {
  key: string;
  label: string;
  render: (row: T) => ReactNode;
  className?: string;
  sortable?: boolean;
};

export function StandardRecordTable<T, A extends string>({
  rows,
  rowKey,
  rowLabel,
  columns,
  actions,
  doubleClick,
  onDoubleClick,
  sortKey,
  sortDirection = "asc",
  onSort,
  rowClassName,
  showActions = true,
  empty,
}: {
  rows: T[];
  rowKey: (row: T) => string | number;
  rowLabel: (row: T) => string;
  columns: StandardRecordColumn<T>[];
  actions: (row: T) => RowAction[];
  doubleClick: { value: A; choices: DoubleClickChoice<A>[]; onChange: (value: A) => void };
  onDoubleClick: (row: T, action: A) => void;
  sortKey?: string;
  sortDirection?: SortDirection;
  onSort?: (key: string) => void;
  rowClassName?: (row: T) => string | undefined;
  showActions?: boolean;
  empty: ReactNode;
}) {
  return <div className="overflow-hidden rounded-lg border">
    <Table className="min-w-184">
      <TableHeader><TableRow className="bg-muted/35 hover:bg-muted/35">
        {columns.map((column) => column.sortable && onSort
          ? <SortableTableHead key={column.key} label={column.label} active={sortKey === column.key} direction={sortDirection} onSort={() => onSort(column.key)} className={column.className} />
          : <TableHead key={column.key} className={cn("px-4", column.className)}>{column.label}</TableHead>)}
        {showActions && <TableHead className="sticky right-0 z-20 w-20 min-w-20 border-l bg-background text-center">Opciones</TableHead>}
      </TableRow></TableHeader>
      <TableBody>{rows.map((row) => {
        const available = actions(row).filter((action) => !action.hidden);
        const contextActions = available.map((action) => ({
          label: action.label,
          icon: action.icon,
          onSelect: action.onSelect,
          destructive: action.destructive,
        }));
        const label = rowLabel(row);
        return <RecordContextMenu key={rowKey(row)} actions={contextActions} doubleClick={doubleClick}>
          <TableRow className={rowClassName?.(row)} title={doubleClick.value === "none" ? undefined : `Doble clic: ${doubleClick.choices.find((choice) => choice.value === doubleClick.value)?.label ?? "abrir"}`} onDoubleClick={(event) => { if ((event.target as HTMLElement).closest('button,a,input,select,textarea,[role="button"],[role="checkbox"]')) return; if (doubleClick.value !== "none") onDoubleClick(row, doubleClick.value); }}>
            {columns.map((column) => <TableCell key={column.key} className={cn("px-4", column.className)}>{column.render(row)}</TableCell>)}
            {showActions && <TableCell className={cn("sticky right-0 text-center", rowClassName?.(row) ? "bg-inherit" : "bg-background")}><RowActionsMenu label={label} actions={available} doubleClick={doubleClick} /></TableCell>}
          </TableRow>
        </RecordContextMenu>;
      })}</TableBody>
    </Table>
    {!rows.length && empty}
  </div>;
}
