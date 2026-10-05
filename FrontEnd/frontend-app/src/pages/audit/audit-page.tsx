import { useCallback, useDeferredValue, useEffect, useState } from "react";
import { BarChart3, Eye, LoaderCircle, ShieldCheck } from "lucide-react";
import { toast } from "sonner";

import { ActionButton } from "@/components/action-button";
import { MetricBarChart } from "@/components/metric-bar-chart";
import { MetricCard } from "@/components/metric-card";
import { RecordContextMenu } from "@/components/record-context-menu";
import { RowActionsMenu } from "@/components/row-actions-menu";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { ExcelDownloadButton } from "@/components/excel-download-button";
import { ListPagination } from "@/components/list-pagination";
import { SortableTableHead } from "@/components/sortable-table-head";
import { StandardListToolbar } from "@/components/standard-list-toolbar";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Sheet, SheetBody, SheetContent, SheetDescription, SheetHeader, SheetSection, SheetSectionTitle, SheetTitle } from "@/components/ui/sheet";
import api from "@/lib/api";
import { usePlatformSettings } from "@/context/PlatformSettingsContext";
import { formatLimaDateTime } from "@/lib/dates";
import { downloadExcelXlsx, type SortDirection } from "@/lib/table-tools";
import type { PageSize } from "@/lib/use-list-pagination";
import { useIncomingSearch } from "@/lib/use-incoming-search";
import { useDoubleClickPreference } from "@/lib/use-double-click-preference";
import { analyticsAPI } from "@/features/analytics/api";
import type { AuditStatistics } from "@/features/analytics/types";
import { apiErrorMessage } from "@/lib/api-error";
import { AuditStorage } from './audit-storage';

type AuditRow = { id: number; accion: string; modulo?: string; entidad: string; entidad_id?: string; detalle?: string; metodo?: string; ruta?: string; estado_http?: number; creado_en?: string; realizado_por?: string; usuario_efectivo?: string; impersonacion_id?: number; ip?: string; request_id?: string; datos_antes?: string; datos_despues?: string };
type SortKey = "date" | "actor" | "action";
type AuditDoubleClick = "detail" | "none";
const AUDIT_DOUBLE_CLICK: readonly AuditDoubleClick[] = ["detail", "none"];

function readableSnapshot(value?: string) {
  if (!value) return "Sin datos";
  try { return JSON.stringify(JSON.parse(value), null, 2); } catch { return value; }
}

export default function AuditPage() {
  const [rows, setRows] = useState<AuditRow[]>([]);
  const { settings } = usePlatformSettings();
  const [search, setSearch] = useIncomingSearch();
  const [quickFilter, setQuickFilter] = useState("all");
  const [direction, setDirection] = useState<SortDirection>("desc");
  const [sortKey, setSortKey] = useState<SortKey>("date");
  const [selected, setSelected] = useState<AuditRow | null>(null);
  const [statisticsOpen, setStatisticsOpen] = useState(false);
  const [statisticsDays, setStatisticsDays] = useState(30);
  const [statistics, setStatistics] = useState<AuditStatistics | null>(null);
  const [statisticsLoading, setStatisticsLoading] = useState(false);
  const [total, setTotal] = useState(0);
  const [counts, setCounts] = useState({ all: 0, create: 0, update: 0, delete: 0, errors: 0 });
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState<PageSize>(10);
  const [doubleClickAction, setDoubleClickAction] = useDoubleClickPreference<AuditDoubleClick>("auditoria", AUDIT_DOUBLE_CLICK, "detail");
  const deferredSearch = useDeferredValue(search);
  const totalPages = pageSize === "all" ? 1 : Math.max(1, Math.ceil(total / pageSize));
  const auditParams = useCallback((requestedPageSize: PageSize = pageSize, requestedPage = page, requestedSearch = deferredSearch) => ({
    page: requestedPage, page_size: requestedPageSize, search: requestedSearch,
    filter_by: quickFilter, sort_key: sortKey, direction,
  }), [pageSize, page, deferredSearch, quickFilter, sortKey, direction]);
  useEffect(() => {
    let cancelled = false;
    void api.get("/auditoria", { params: auditParams() }).then(({ data }) => {
      if (!cancelled) { setRows(data.items); setTotal(data.total); setCounts(data.counts); }
    });
    return () => { cancelled = true; };
  }, [auditParams]);
  useEffect(() => {
    if (!statisticsOpen) return;
    let cancelled = false;
    setStatistics(null);
    setStatisticsLoading(true);
    analyticsAPI.audit(statisticsDays).then((data) => { if (!cancelled) setStatistics(data); }).catch((error) => {
      if (!cancelled) toast.error(apiErrorMessage(error, "No se pudieron cargar las estadísticas"));
    }).finally(() => { if (!cancelled) setStatisticsLoading(false); });
    return () => { cancelled = true; };
  }, [statisticsOpen, statisticsDays]);
  const sortBy = (key: SortKey) => {
    setPage(1);
    if (sortKey === key) setDirection((current) => current === "asc" ? "desc" : "asc");
    else { setSortKey(key); setDirection("asc"); }
  };
  const exportAudit = async () => {
    const { data } = await api.get("/auditoria", { params: auditParams("all", 1, search) });
    return downloadExcelXlsx("auditoria", data.items as AuditRow[], [
    { header: "Fecha", value: (row) => formatLimaDateTime(row.creado_en) },
    { header: "Realizado por", value: (row) => row.realizado_por ?? "Sistema" },
    { header: "Accion", value: (row) => row.accion },
    { header: "Modulo", value: (row) => row.modulo },
    { header: "Entidad", value: (row) => row.entidad },
    { header: "Entidad ID", value: (row) => row.entidad_id },
    { header: "Metodo", value: (row) => row.metodo },
    { header: "Ruta", value: (row) => row.ruta },
    { header: "Estado HTTP", value: (row) => row.estado_http },
    { header: "Detalle", value: (row) => row.detalle },
    { header: "Datos anteriores", value: (row) => row.datos_antes },
    { header: "Datos posteriores", value: (row) => row.datos_despues },
    ], { organizationName: settings.organization_name, criteria: { Busqueda: search || "Sin busqueda", Tipo: quickFilter, Orden: `${sortKey}-${direction}`, Registros: data.total } });
  };
  return <main className="space-y-4 p-4 md:p-6">
    <div className="flex flex-wrap items-center justify-between gap-3"><div><h1 className="flex items-center gap-2 text-2xl font-semibold"><ShieldCheck className="text-sky-600" />Auditoría</h1><p className="text-sm text-muted-foreground">Actividad administrativa de ABISSOL.</p></div><div className="flex flex-wrap gap-2"><AuditStorage/><ActionButton tone="info" onClick={() => setStatisticsOpen(true)}><BarChart3 className="size-4" />Estadísticas</ActionButton><ExcelDownloadButton onDownload={exportAudit} disabled={total === 0} /></div></div>
    <Card className="gap-0 py-0"><CardContent className="space-y-3 p-4 md:p-5">
      <StandardListToolbar embedded resultLabel={`${total} operacion${total === 1 ? "" : "es"} encontrada${total === 1 ? "" : "s"}`} pagination={<ListPagination embedded compactWhenSinglePage page={page} pageSize={pageSize} totalItems={total} totalPages={totalPages} onPageChange={setPage} onPageSizeChange={(value) => { setPageSize(value); setPage(1); }} />} search={search} onSearchChange={(value) => { setSearch(value); setPage(1); }} searchPlaceholder="Buscar acción, módulo, entidad, ruta o estado..." filters={[
        { value: "all", label: "Todos", count: counts.all },
        { value: "create", label: "Creaciones", count: counts.create },
        { value: "update", label: "Modificaciones", count: counts.update },
        { value: "delete", label: "Eliminaciones", count: counts.delete },
        { value: "errors", label: "Errores", count: counts.errors },
      ]} activeFilter={quickFilter} onFilterChange={(value) => { setQuickFilter(value); setPage(1); }} resultCount={total} totalCount={counts.all} />
      {rows.length === 0 ? <p className="text-sm text-muted-foreground">No hay operaciones para los filtros actuales.</p> : <Table><TableHeader><TableRow><SortableTableHead label="Fecha" active={sortKey === "date"} direction={direction} onSort={() => sortBy("date")} /><SortableTableHead label="Realizado por" active={sortKey === "actor"} direction={direction} onSort={() => sortBy("actor")} /><SortableTableHead label="Acción" active={sortKey === "action"} direction={direction} onSort={() => sortBy("action")} /><TableHead>Registro</TableHead><TableHead>Estado</TableHead><TableHead className="w-16 text-right">Opciones</TableHead></TableRow></TableHeader><TableBody>{rows.map((row) => { const doubleClickChoices = [{ value: "detail" as const, label: "Ver detalle" }, { value: "none" as const, label: "Ninguna acción" }]; return <RecordContextMenu key={row.id} actions={[{ label: "Ver detalle", icon: Eye, onSelect: () => setSelected(row) }]} doubleClick={{ value: doubleClickAction, onChange: setDoubleClickAction, choices: doubleClickChoices }}><TableRow title={`Doble clic: ${doubleClickAction === "detail" ? "ver detalle" : "sin acción"}`} onDoubleClick={() => doubleClickAction === "detail" && setSelected(row)}><TableCell className="text-xs text-muted-foreground">{formatLimaDateTime(row.creado_en)}</TableCell><TableCell className="font-medium">{row.realizado_por ?? "Sistema"}</TableCell><TableCell><Badge variant="outline">{row.accion}</Badge></TableCell><TableCell><p className="max-w-md truncate font-medium">{row.detalle || row.entidad}</p><p className="max-w-md truncate text-xs text-muted-foreground">{row.entidad}{row.ruta ? ` · ${row.ruta}` : ""}</p></TableCell><TableCell>{row.estado_http ? <Badge variant={row.estado_http >= 400 ? "destructive" : "secondary"}>{row.estado_http}</Badge> : "—"}</TableCell><TableCell className="text-right" onDoubleClick={(event) => event.stopPropagation()}><RowActionsMenu label={`auditoría ${row.id}`} actions={[{ label: "Ver detalle", icon: Eye, onSelect: () => setSelected(row) }]} doubleClick={{ value: doubleClickAction, onChange: setDoubleClickAction, choices: doubleClickChoices }} /></TableCell></TableRow></RecordContextMenu>; })}</TableBody></Table>}
    </CardContent></Card>
    <Sheet open={selected !== null} onOpenChange={(open) => { if (!open) setSelected(null); }}>
      <SheetContent className="w-full sm:max-w-3xl">
        <SheetHeader><SheetTitle>Detalle de auditoría</SheetTitle><SheetDescription>Registro completo de solo lectura.</SheetDescription></SheetHeader>
        {selected && <SheetBody className="space-y-5">
          <SheetSection><SheetSectionTitle>Operación</SheetSectionTitle><dl className="grid gap-4 text-sm sm:grid-cols-2">
            <div><dt className="text-muted-foreground">Fecha</dt><dd className="font-medium">{formatLimaDateTime(selected.creado_en)}</dd></div>
            <div><dt className="text-muted-foreground">Realizado por</dt><dd className="font-medium">{selected.realizado_por ?? "Sistema"}</dd></div>
            <div><dt className="text-muted-foreground">Usuario efectivo</dt><dd className="font-medium">{selected.usuario_efectivo ?? "Sistema"}</dd></div>
            <div><dt className="text-muted-foreground">Impersonación</dt><dd className="font-medium">{selected.impersonacion_id ?? "—"}</dd></div>
            <div><dt className="text-muted-foreground">Acción</dt><dd className="font-medium">{selected.accion}</dd></div>
            <div><dt className="text-muted-foreground">Módulo</dt><dd className="font-medium">{selected.modulo || "—"}</dd></div>
            <div><dt className="text-muted-foreground">Entidad</dt><dd className="font-medium">{selected.entidad}</dd></div>
            <div><dt className="text-muted-foreground">Entidad ID</dt><dd className="font-medium">{selected.entidad_id || "—"}</dd></div>
            <div><dt className="text-muted-foreground">Método</dt><dd className="font-medium">{selected.metodo || "—"}</dd></div>
            <div><dt className="text-muted-foreground">Estado HTTP</dt><dd className="font-medium">{selected.estado_http ?? "—"}</dd></div>
          </dl></SheetSection>
          <SheetSection><SheetSectionTitle>Solicitud y detalle</SheetSectionTitle><div className="space-y-3 text-sm">
            <div><p className="text-muted-foreground">Ruta</p><p className="break-all font-mono text-xs">{selected.ruta || "—"}</p></div>
            <div><p className="text-muted-foreground">IP</p><p className="break-all font-mono text-xs">{selected.ip || "—"}</p></div>
            <div><p className="text-muted-foreground">ID de solicitud</p><p className="break-all font-mono text-xs">{selected.request_id || "—"}</p></div>
            <div><p className="text-muted-foreground">Detalle</p><p className="whitespace-pre-wrap break-words">{selected.detalle || "Sin detalle adicional"}</p></div>
          </div></SheetSection>
          <div className="grid gap-5 lg:grid-cols-2">
            <SheetSection><SheetSectionTitle>Datos anteriores</SheetSectionTitle><pre className="max-h-96 overflow-auto whitespace-pre-wrap break-words rounded-lg border bg-muted/35 p-3 text-xs">{readableSnapshot(selected.datos_antes)}</pre></SheetSection>
            <SheetSection><SheetSectionTitle>Datos posteriores</SheetSectionTitle><pre className="max-h-96 overflow-auto whitespace-pre-wrap break-words rounded-lg border bg-muted/35 p-3 text-xs">{readableSnapshot(selected.datos_despues)}</pre></SheetSection>
          </div>
        </SheetBody>}
      </SheetContent>
    </Sheet>
    <Sheet open={statisticsOpen} onOpenChange={setStatisticsOpen}>
      <SheetContent className="w-full sm:max-w-5xl">
        <SheetHeader><SheetTitle>Estadísticas de Auditoría</SheetTitle><SheetDescription>Indicadores calculados con movimientos reales del periodo seleccionado.</SheetDescription></SheetHeader>
        <SheetBody className="space-y-5">
          <div className="flex flex-wrap gap-2" aria-label="Periodo estadístico">{[7, 30, 90].map((days) => <Button key={days} size="sm" variant={statisticsDays === days ? "default" : "outline"} onClick={() => setStatisticsDays(days)}>{days} días</Button>)}</div>
          {statisticsLoading && !statistics ? <div className="flex items-center gap-2 rounded-xl border p-5 text-sm text-muted-foreground"><LoaderCircle className="size-4 animate-spin" />Calculando estadísticas…</div> : statistics && <>
            <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">{statistics.cards.map((metric) => <MetricCard key={metric.key} metric={metric} />)}</div>
            <div className={`grid gap-4 xl:grid-cols-2 ${statisticsLoading ? "opacity-60" : ""}`}>{statistics.charts.map((chart) => <MetricBarChart key={chart.key} chart={chart} />)}</div>
          </>}
        </SheetBody>
      </SheetContent>
    </Sheet>
  </main>;
}
