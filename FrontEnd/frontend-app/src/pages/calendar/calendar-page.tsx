import { useCallback, useEffect, useMemo, useRef, useState, type MouseEvent as ReactMouseEvent } from "react";
import type { DateClickArg, EventResizeDoneArg } from "@fullcalendar/interaction";
import interactionPlugin from "@fullcalendar/interaction";
import type { DateSelectArg, EventClickArg, EventDropArg, EventInput, EventMountArg } from "@fullcalendar/core";
import esLocale from "@fullcalendar/core/locales/es";
import dayGridPlugin from "@fullcalendar/daygrid";
import listPlugin from "@fullcalendar/list";
import FullCalendar from "@fullcalendar/react";
import timeGridPlugin from "@fullcalendar/timegrid";
import { DndContext, type DragEndEvent, useDraggable, useDroppable } from "@dnd-kit/core";
import { CalendarDays, Download, GripVertical, Pencil, Plus, Tags, Trash2 } from "lucide-react";
import { toast } from "sonner";

import { ActionButton } from "@/components/action-button";
import { ConfirmActionDialog } from "@/components/confirm-action-dialog";
import { ExcelDownloadButton } from "@/components/excel-download-button";
import { RecordContextMenu, type RecordContextAction } from "@/components/record-context-menu";
import { SearchableMultiSelect, SearchableSelect } from "@/components/searchable-select";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Sheet,
  SheetBody,
  SheetContent,
  SheetDescription,
  SheetFooter,
  SheetHeader,
  SheetSection,
  SheetSectionTitle,
  SheetTitle,
} from "@/components/ui/sheet";
import { Switch } from "@/components/ui/switch";
import { useAuth } from "@/context/AuthContext";
import { usePlatformSettings } from "@/context/PlatformSettingsContext";
import { calendarAPI } from "@/features/calendar/api";
import type {
  CalendarEvent,
  CalendarEventWrite,
  CalendarLabel,
  CalendarPerson,
  CalendarPriority,
  CalendarStatus,
  CalendarVisibility,
} from "@/features/calendar/types";
import { formatLimaDateTime, fromLimaInput, toLimaInput } from "@/lib/dates";
import { downloadExcelXlsx } from "@/lib/table-tools";

type PlannerView = "calendario" | "agenda" | "tablero";
type CalendarContextTarget =
  | { kind: "event"; event: CalendarEvent }
  | { kind: "blank"; start: string; end: string; allDay: boolean }
  | null;

const statuses: { value: CalendarStatus; label: string; color: string }[] = [
  { value: "pendiente", label: "Pendiente", color: "#64748b" },
  { value: "confirmado", label: "Confirmado", color: "#2563eb" },
  { value: "en_progreso", label: "En progreso", color: "#d97706" },
  { value: "completado", label: "Completado", color: "#059669" },
  { value: "cancelado", label: "Cancelado", color: "#dc2626" },
];

const priorities = [
  { value: "baja", label: "Prioridad baja" },
  { value: "media", label: "Prioridad media" },
  { value: "alta", label: "Prioridad alta" },
  { value: "urgente", label: "Prioridad urgente" },
];

const reminderOptions = [
  { value: "-1", label: "Sin recordatorio" },
  { value: "0", label: "Al comenzar" },
  { value: "15", label: "15 minutos antes" },
  { value: "30", label: "30 minutos antes" },
  { value: "60", label: "1 hora antes" },
  { value: "1440", label: "1 día antes" },
];

const emptyForm = (): CalendarEventWrite => ({
  titulo: "",
  descripcion: null,
  inicio: toLimaInput(new Date().toISOString()),
  fin: toLimaInput(new Date(Date.now() + 3_600_000).toISOString()),
  todo_el_dia: false,
  estado: "pendiente",
  prioridad: "media",
  visibilidad: "equipo",
  ubicacion: null,
  asignado_ids: [],
  etiqueta_ids: [],
  recordatorios: [{ minutos_antes: 30, canal: "interno" }],
  origen_modulo: null,
  origen_tipo: null,
  origen_id: null,
  origen_url: null,
});

function message(error: unknown) {
  if (typeof error === "object" && error && "response" in error) {
    return (error as { response?: { data?: { detail?: string } } }).response?.data?.detail;
  }
  return undefined;
}

function PlannerTabButton({ active, children, onClick }: { active: boolean; children: string; onClick: () => void }) {
  return <button type="button" role="tab" aria-selected={active} onClick={onClick} className={`-mb-px flex shrink-0 items-center justify-center border-b-2 px-4 py-3 text-sm font-medium transition-colors ${active ? "border-sky-500 text-foreground" : "border-transparent text-muted-foreground hover:border-border hover:text-foreground"}`}>{children}</button>;
}

function BoardCard({ event, editable, onOpen }: { event: CalendarEvent; editable: boolean; onOpen: () => void }) {
  const drag = useDraggable({ id: event.id, disabled: !editable, data: { event } });
  return <button
    ref={drag.setNodeRef}
    style={{ transform: drag.transform ? `translate3d(${drag.transform.x}px,${drag.transform.y}px,0)` : undefined }}
    {...drag.listeners}
    {...drag.attributes}
    type="button"
    onClick={onOpen}
    className="w-full rounded-xl border bg-card p-3 text-left shadow-xs transition hover:border-primary/35 hover:shadow-sm"
  >
    <span className="flex items-start gap-2"><GripVertical className="mt-0.5 size-4 shrink-0 text-muted-foreground" /><span className="min-w-0"><strong className="block truncate text-sm">{event.titulo}</strong><span className="mt-1 block text-xs text-muted-foreground">{formatLimaDateTime(event.inicio)}</span></span></span>
    <span className="mt-2 flex flex-wrap gap-1">{event.etiquetas.map((label) => <span key={label.id} className="rounded-full px-2 py-0.5 text-[10px] text-white" style={{ background: label.color }}>{label.nombre}</span>)}</span>
  </button>;
}

function BoardColumn({
  status,
  events,
  editable,
  onOpen,
  actionsFor,
}: {
  status: typeof statuses[number];
  events: CalendarEvent[];
  editable: boolean;
  onOpen: (event: CalendarEvent) => void;
  actionsFor: (event: CalendarEvent) => RecordContextAction[];
}) {
  const drop = useDroppable({ id: status.value });
  return <section ref={drop.setNodeRef} className={`min-h-64 rounded-2xl border bg-muted/25 p-3 ${drop.isOver ? "ring-2 ring-primary/35" : ""}`}>
    <div className="mb-3 flex items-center justify-between"><span className="flex items-center gap-2 text-sm font-semibold"><i className="size-2.5 rounded-full" style={{ background: status.color }} />{status.label}</span><Badge variant="secondary">{events.length}</Badge></div>
    <div className="space-y-2">{events.map((event) => <RecordContextMenu key={event.id} actions={actionsFor(event)}><BoardCard event={event} editable={editable} onOpen={() => onOpen(event)} /></RecordContextMenu>)}</div>
  </section>;
}

export default function CalendarPage() {
  const { can } = useAuth();
  const { settings } = usePlatformSettings();
  const [events, setEvents] = useState<CalendarEvent[]>([]);
  const [people, setPeople] = useState<CalendarPerson[]>([]);
  const [labels, setLabels] = useState<CalendarLabel[]>([]);
  const [view, setView] = useState<PlannerView>("calendario");
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState<CalendarStatus | "todos">("todos");
  const [personFilter, setPersonFilter] = useState<number | undefined>();
  const [selected, setSelected] = useState<CalendarEvent | null>(null);
  const [form, setForm] = useState<CalendarEventWrite>(emptyForm);
  const [open, setOpen] = useState(false);
  const [saving, setSaving] = useState(false);
  const [labelsOpen, setLabelsOpen] = useState(false);
  const [labelName, setLabelName] = useState("");
  const [labelColor, setLabelColor] = useState("#2563eb");
  const [labelBusy, setLabelBusy] = useState(false);
  const [calendarContextTarget, setCalendarContextTarget] = useState<CalendarContextTarget>(null);
  const editable = can("calendario", "editor");
  const manageable = can("calendario", "gestor");
  const requestSequence = useRef(0);

  const load = useCallback(async (signal?: AbortSignal) => {
    const sequence=++requestSequence.current;
    try {
      const rows=await calendarAPI.events({ buscar: search, estado: statusFilter, asignado_id: personFilter }, signal);
      if (sequence===requestSequence.current && !signal?.aborted) setEvents(rows);
    } catch {
      if (sequence===requestSequence.current && !signal?.aborted) toast.error("No se pudo cargar el calendario");
    }
  }, [search, statusFilter, personFilter]);

  useEffect(() => { const controller=new AbortController(); void load(controller.signal); return()=>controller.abort(); }, [load]);
  useEffect(() => {
    void Promise.all([calendarAPI.people(), calendarAPI.labels()])
      .then(([users, tags]) => { setPeople(users); setLabels(tags); })
      .catch(() => toast.error("No se pudieron cargar los catálogos del calendario"));
  }, []);

  const reloadLabels = async () => setLabels(await calendarAPI.labels());
  const createLabel = async () => {
    const name = labelName.trim();
    if (!name) return;
    setLabelBusy(true);
    try {
      await calendarAPI.createLabel(name, labelColor);
      await reloadLabels();
      setLabelName("");
      setLabelColor("#2563eb");
      toast.success("Etiqueta creada");
    } catch (error) {
      toast.error(message(error) || "No se pudo crear la etiqueta");
    } finally {
      setLabelBusy(false);
    }
  };

  const removeLabel = async (label: CalendarLabel) => {
    try {
      await calendarAPI.removeLabel(label.id);
      setLabels((current) => current.filter((item) => item.id !== label.id));
      setForm((current) => ({ ...current, etiqueta_ids: current.etiqueta_ids.filter((id) => id !== label.id) }));
      toast.success("Etiqueta retirada");
    } catch (error) {
      toast.error(message(error) || "No se pudo retirar la etiqueta");
      throw error;
    }
  };

  const openNew = (start?: string, end?: string, allDay = false) => {
    const next = emptyForm();
    const normalizedStart = start && /^\d{4}-\d{2}-\d{2}$/.test(start) ? `${start}T00:00:00-05:00` : start;
    const normalizedEnd = end && /^\d{4}-\d{2}-\d{2}$/.test(end) ? `${end}T00:00:00-05:00` : end;
    if (normalizedStart) next.inicio = toLimaInput(normalizedStart);
    if (normalizedEnd) next.fin = toLimaInput(normalizedEnd);
    next.todo_el_dia = allDay;
    setSelected(null);
    setForm(next);
    setOpen(true);
  };

  const openEvent = (event: CalendarEvent) => {
    setSelected(event);
    setForm({
      titulo: event.titulo,
      descripcion: event.descripcion,
      inicio: toLimaInput(event.inicio),
      fin: toLimaInput(event.fin),
      todo_el_dia: event.todo_el_dia,
      estado: event.estado,
      prioridad: event.prioridad,
      visibilidad: event.visibilidad,
      ubicacion: event.ubicacion,
      asignado_ids: event.asignados.map((item) => item.id),
      etiqueta_ids: event.etiquetas.map((item) => item.id),
      recordatorios: event.recordatorios.map(({ minutos_antes, canal }) => ({ minutos_antes, canal })),
      origen_modulo: event.origen_modulo,
      origen_tipo: event.origen_tipo,
      origen_id: event.origen_id,
      origen_url: event.origen_url,
    });
    setOpen(true);
  };

  const payload = (): CalendarEventWrite => ({
    ...form,
    titulo: form.titulo.trim(),
    descripcion: form.descripcion?.trim() || null,
    ubicacion: form.ubicacion?.trim() || null,
    inicio: fromLimaInput(form.inicio)!,
    fin: fromLimaInput(form.fin)!,
  });

  const save = async () => {
    if (!form.titulo.trim() || !form.inicio || !form.fin) return toast.error("Completa el título y las fechas");
    setSaving(true);
    try {
      if (selected) await calendarAPI.update(selected.id, { ...payload(), version: selected.version });
      else await calendarAPI.create(payload());
      toast.success(selected ? "Evento actualizado" : "Evento creado");
      setOpen(false);
      await load();
    } catch (error) {
      toast.error(message(error) || "No se pudo guardar el evento");
    } finally {
      setSaving(false);
    }
  };

  const move = async (event: CalendarEvent, changes: Partial<CalendarEventWrite>, revert?: () => void) => {
    try {
      await calendarAPI.update(event.id, { ...changes, version: event.version });
      await load();
    } catch (error) {
      revert?.();
      toast.error(message(error) || "No se pudo mover el evento");
    }
  };

  const handleCalendarMove = (info: EventDropArg | EventResizeDoneArg) => {
    const source = events.find((item) => item.id === Number(info.event.id));
    if (source && info.event.start && info.event.end) {
      void move(source, {
        inicio: info.event.start.toISOString(),
        fin: info.event.end.toISOString(),
        todo_el_dia: info.event.allDay,
      }, info.revert);
    }
  };

  const eventActions = (event: CalendarEvent): RecordContextAction[] => [
    { label: editable ? "Editar evento" : "Ver evento", icon: Pencil, onSelect: () => openEvent(event) },
    ...(manageable ? [{ label: "Eliminar evento...", icon: Trash2, destructive: true, onSelect: () => document.getElementById(`calendar-delete-${event.id}`)?.click() }] : []),
  ];

  const resolveCalendarContext = (event: ReactMouseEvent<HTMLDivElement>) => {
    const target = event.target as HTMLElement;
    const eventElement = target.closest<HTMLElement>("[data-calendar-event-id]");
    if (eventElement) {
      const calendarEvent = events.find((item) => item.id === Number(eventElement.dataset.calendarEventId));
      setCalendarContextTarget(calendarEvent ? { kind: "event", event: calendarEvent } : null);
      return;
    }
    const calendarRoot = target.closest<HTMLElement>(".abissol-calendar");
    const datedElement = target.closest<HTMLElement>("[data-date]")
      ?? [...(calendarRoot?.querySelectorAll<HTMLElement>(".fc-timegrid-col[data-date], .fc-daygrid-day[data-date]") ?? [])]
        .find((column) => {
          const rect = column.getBoundingClientRect();
          return event.clientX >= rect.left && event.clientX < rect.right
            && event.clientY >= rect.top && event.clientY < rect.bottom;
        });
    const date = datedElement?.dataset.date;
    if (!date) {
      setCalendarContextTarget(null);
      return;
    }
    const timeSlot = [...(calendarRoot?.querySelectorAll<HTMLElement>(".fc-timegrid-slot-lane[data-time]") ?? [])]
      .find((slot) => { const rect = slot.getBoundingClientRect(); return event.clientY >= rect.top && event.clientY < rect.bottom; });
    if (timeSlot?.dataset.time) {
      const start = `${date}T${timeSlot.dataset.time}-05:00`;
      setCalendarContextTarget({ kind: "blank", start, end: new Date(Date.parse(start) + 3_600_000).toISOString(), allDay: false });
      return;
    }
    const start = `${date}T00:00:00-05:00`;
    setCalendarContextTarget({ kind: "blank", start, end: new Date(Date.parse(start) + 86_400_000).toISOString(), allDay: true });
  };

  const calendarContextActions: RecordContextAction[] = calendarContextTarget?.kind === "event"
    ? eventActions(calendarContextTarget.event)
    : editable && calendarContextTarget?.kind === "blank" ? [{
        label: "Crear evento aquí",
        icon: Plus,
        onSelect: () => {
          if (calendarContextTarget?.kind === "blank") openNew(calendarContextTarget.start, calendarContextTarget.end, calendarContextTarget.allDay);
        },
      }] : [];

  const calendarEvents: EventInput[] = events.map((event) => ({
    id: String(event.id),
    title: event.titulo,
    start: event.inicio,
    end: event.fin,
    allDay: event.todo_el_dia,
    backgroundColor: statuses.find((item) => item.value === event.estado)?.color,
    borderColor: "transparent",
  }));

  const exportExcel = () => downloadExcelXlsx("calendario", events, [
    { header: "Título", value: (row) => row.titulo },
    { header: "Inicio", value: (row) => formatLimaDateTime(row.inicio) },
    { header: "Fin", value: (row) => formatLimaDateTime(row.fin) },
    { header: "Estado", value: (row) => row.estado },
    { header: "Prioridad", value: (row) => row.prioridad },
    { header: "Responsables", value: (row) => row.asignados.map((item) => item.nombre).join(", ") },
  ], {
    organizationName: settings.organization_name,
    criteria: { Búsqueda: search || "Todas", Estado: statusFilter },
  });

  const exportIcs = async () => {
    const blob = await calendarAPI.exportIcs();
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = "abissol-calendario.ics";
    link.click();
    URL.revokeObjectURL(url);
  };

  const grouped = useMemo(() => [...events].sort((a, b) => a.inicio.localeCompare(b.inicio)), [events]);
  const availableLabels = useMemo(() => {
    const byId = new Map(labels.map((label) => [label.id, label]));
    selected?.etiquetas.forEach((label) => byId.set(label.id, label));
    return [...byId.values()].sort((a, b) => a.nombre.localeCompare(b.nombre, "es", { sensitivity: "base" }));
  }, [labels, selected]);

  return <main className="space-y-4 p-4 md:p-6">
    <div className="flex flex-wrap items-center justify-between gap-3">
      <div><h1 className="flex items-center gap-2 text-2xl font-semibold"><CalendarDays className="text-sky-600" />Calendario</h1><p className="text-sm text-muted-foreground">Planifica, asigna y mueve actividades en un solo lugar.</p></div>
      <div className="flex flex-wrap gap-2"><ExcelDownloadButton onDownload={exportExcel} disabled={!events.length} /><Button variant="outline" onClick={() => void exportIcs()}><Download />ICS</Button>{(editable || manageable) && <ActionButton tone="info" onClick={() => setLabelsOpen(true)}><Tags />Etiquetas</ActionButton>}{editable && <ActionButton tone="new" onClick={() => openNew()}><Plus />Nuevo evento</ActionButton>}</div>
    </div>

    <nav className="flex w-full overflow-x-auto border-b [scrollbar-width:none] [&::-webkit-scrollbar]:hidden" role="tablist" aria-label="Vistas del calendario">
      <PlannerTabButton active={view === "calendario"} onClick={() => setView("calendario")}>Calendario</PlannerTabButton>
      <PlannerTabButton active={view === "agenda"} onClick={() => setView("agenda")}>Agenda</PlannerTabButton>
      <PlannerTabButton active={view === "tablero"} onClick={() => setView("tablero")}>Tablero</PlannerTabButton>
    </nav>

    <Card className="gap-0 py-0"><CardContent className="space-y-4 p-4 md:p-5">
      <div className="grid gap-2 md:grid-cols-[minmax(13rem,1fr)_14rem_16rem]">
        <Input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Buscar evento, etiqueta o ubicación..." />
        <SearchableSelect aria-label="Filtrar por estado" value={statusFilter} onValueChange={(value) => setStatusFilter(value as CalendarStatus | "todos")} options={[{ value: "todos", label: "Todos los estados" }, ...statuses.map((item) => ({ value: item.value, label: item.label }))]} searchPlaceholder="Buscar estado..." />
        <SearchableSelect aria-label="Filtrar por responsable" value={personFilter ? String(personFilter) : ""} onValueChange={(value) => setPersonFilter(value ? Number(value) : undefined)} options={[{ value: "", label: "Todos los responsables" }, ...people.map((person) => ({ value: String(person.id), label: person.nombre, keywords: person.username }))]} searchPlaceholder="Buscar responsable..." />
      </div>

      {view === "calendario" && <RecordContextMenu actions={calendarContextActions} dynamic><div className="abissol-calendar" onContextMenuCapture={resolveCalendarContext}>
        <FullCalendar
          plugins={[dayGridPlugin, timeGridPlugin, listPlugin, interactionPlugin]}
          locale={esLocale}
          initialView="dayGridMonth"
          headerToolbar={{ left: "prev,next today", center: "title", right: "dayGridMonth,timeGridWeek,timeGridDay,listWeek" }}
          buttonText={{ today: "Hoy", month: "Mes", week: "Semana", day: "Día", list: "Lista" }}
          slotDuration="00:30:00"
          slotLabelInterval="01:00:00"
          scrollTime="07:00:00"
          nowIndicator
          height="auto"
          events={calendarEvents}
          editable={editable}
          selectable={editable}
          selectMirror
          eventDidMount={(info: EventMountArg) => { info.el.dataset.calendarEventId = info.event.id; }}
          select={(info: DateSelectArg) => openNew(info.startStr, info.endStr, info.allDay)}
          dateClick={(info: DateClickArg) => { if (editable) openNew(info.dateStr, new Date(info.date.getTime() + (info.allDay ? 86_400_000 : 3_600_000)).toISOString(), info.allDay); }}
          eventClick={(info: EventClickArg) => { const event = events.find((item) => item.id === Number(info.event.id)); if (event) openEvent(event); }}
          eventDrop={handleCalendarMove}
          eventResize={handleCalendarMove}
        />
      </div></RecordContextMenu>}

      {view === "agenda" && <div className="divide-y rounded-xl border">{grouped.length ? grouped.map((event) => <RecordContextMenu key={event.id} actions={eventActions(event)}><button type="button" onClick={() => openEvent(event)} className="grid w-full gap-2 p-4 text-left hover:bg-muted/40 sm:grid-cols-[10rem_1fr_auto]"><span className="text-sm text-muted-foreground">{formatLimaDateTime(event.inicio)}</span><span><strong className="block">{event.titulo}</strong><small className="text-muted-foreground">{event.asignados.map((item) => item.nombre).join(", ") || event.propietario.nombre}</small></span><Badge variant="outline">{statuses.find((item) => item.value === event.estado)?.label}</Badge></button></RecordContextMenu>) : <p className="p-8 text-center text-sm text-muted-foreground">No hay eventos para los filtros actuales.</p>}</div>}

      {view === "tablero" && <DndContext onDragEnd={(info: DragEndEvent) => { const event = info.active.data.current?.event as CalendarEvent | undefined; const next = info.over?.id as CalendarStatus | undefined; if (event && next && event.estado !== next) void move(event, { estado: next }); }}><div className="grid gap-3 xl:grid-cols-5">{statuses.map((status) => <BoardColumn key={status.value} status={status} events={events.filter((event) => event.estado === status.value)} editable={editable} onOpen={openEvent} actionsFor={eventActions} />)}</div></DndContext>}
    </CardContent></Card>

    <Sheet open={labelsOpen} onOpenChange={setLabelsOpen}><SheetContent className="w-full sm:max-w-xl">
      <SheetHeader><SheetTitle>Etiquetas del calendario</SheetTitle><SheetDescription>Crea etiquetas reutilizables y retira las que ya no deben asignarse a nuevos eventos.</SheetDescription></SheetHeader>
      <SheetBody className="space-y-5">
        {editable && <SheetSection><SheetSectionTitle>Nueva etiqueta</SheetSectionTitle><div className="grid gap-4 sm:grid-cols-[1fr_auto]"><div><Label htmlFor="calendar-label-name">Nombre</Label><Input id="calendar-label-name" maxLength={60} value={labelName} onChange={(event) => setLabelName(event.target.value)} placeholder="Ej. Entrega crítica" /></div><div><Label htmlFor="calendar-label-color">Color</Label><Input id="calendar-label-color" type="color" value={labelColor} onChange={(event) => setLabelColor(event.target.value)} className="w-full cursor-pointer px-2 sm:w-20" /></div></div><ActionButton tone="new" disabled={labelBusy || !labelName.trim()} onClick={() => void createLabel()}><Plus />{labelBusy ? "Creando…" : "Crear etiqueta"}</ActionButton></SheetSection>}
        <SheetSection><SheetSectionTitle>Etiquetas activas</SheetSectionTitle><div className="space-y-2">{labels.map((label) => <div key={label.id} className="flex items-center gap-3 rounded-xl border bg-muted/15 p-3"><i className="size-3 shrink-0 rounded-full" style={{ background: label.color }} /><span className="min-w-0 flex-1"><strong className="block truncate text-sm">{label.nombre}</strong><small className="text-muted-foreground">{label.color.toUpperCase()}</small></span>{manageable && <ConfirmActionDialog title="Retirar etiqueta" description={`La etiqueta “${label.nombre}” dejará de estar disponible para nuevos eventos. Los eventos existentes conservarán su referencia histórica.`} confirmLabel="Retirar" destructive onConfirm={() => removeLabel(label)}><ActionButton tone="delete" size="icon" title={`Retirar ${label.nombre}`} aria-label={`Retirar etiqueta ${label.nombre}`}><Trash2 className="size-4" /></ActionButton></ConfirmActionDialog>}</div>)}{!labels.length && <p className="rounded-xl border border-dashed p-8 text-center text-sm text-muted-foreground">No hay etiquetas activas.</p>}</div></SheetSection>
      </SheetBody>
      <SheetFooter><Button variant="outline" onClick={() => setLabelsOpen(false)}>Cerrar</Button></SheetFooter>
    </SheetContent></Sheet>

    <Sheet open={open} onOpenChange={setOpen}><SheetContent className="w-full sm:max-w-2xl">
      <SheetHeader><SheetTitle>{selected ? "Editar evento" : "Nuevo evento"}</SheetTitle><SheetDescription>Las fechas se muestran en horario de Lima. Los cambios de calendario y tablero se guardan al mover.</SheetDescription></SheetHeader>
      <SheetBody className="space-y-5">
        <SheetSection><SheetSectionTitle>Información</SheetSectionTitle><div className="grid gap-4 sm:grid-cols-2"><div className="sm:col-span-2"><Label htmlFor="event-title">Título</Label><Input id="event-title" value={form.titulo} onChange={(event) => setForm({ ...form, titulo: event.target.value })} /></div><div><Label htmlFor="event-start">Inicio</Label><Input id="event-start" type="datetime-local" value={form.inicio} onChange={(event) => setForm({ ...form, inicio: event.target.value })} /></div><div><Label htmlFor="event-end">Fin</Label><Input id="event-end" type="datetime-local" value={form.fin} onChange={(event) => setForm({ ...form, fin: event.target.value })} /></div><div className="flex items-center justify-between rounded-lg border p-3"><Label htmlFor="all-day">Todo el día</Label><Switch id="all-day" checked={form.todo_el_dia} onCheckedChange={(value) => setForm({ ...form, todo_el_dia: value })} /></div><Input value={form.ubicacion ?? ""} onChange={(event) => setForm({ ...form, ubicacion: event.target.value })} placeholder="Ubicación" /><textarea value={form.descripcion ?? ""} onChange={(event) => setForm({ ...form, descripcion: event.target.value })} placeholder="Descripción" className="min-h-24 rounded-md border bg-background p-3 text-sm sm:col-span-2" /></div></SheetSection>

        <SheetSection><SheetSectionTitle>Organización</SheetSectionTitle>
          <div className="grid gap-4 sm:grid-cols-3">
            <SearchableSelect aria-label="Estado" value={form.estado} onValueChange={(value) => setForm({ ...form, estado: value as CalendarStatus })} options={statuses.map((item) => ({ value: item.value, label: item.label }))} searchPlaceholder="Buscar estado..." />
            <SearchableSelect aria-label="Prioridad" value={form.prioridad} onValueChange={(value) => setForm({ ...form, prioridad: value as CalendarPriority })} options={priorities} searchPlaceholder="Buscar prioridad..." />
            <SearchableSelect aria-label="Visibilidad" value={form.visibilidad} onValueChange={(value) => setForm({ ...form, visibilidad: value as CalendarVisibility })} options={[{ value: "equipo", label: "Visible al equipo" }, { value: "personal", label: "Personal" }]} searchPlaceholder="Buscar visibilidad..." />
          </div>
          <div className="space-y-2"><Label>Responsables</Label><SearchableMultiSelect aria-label="Responsables" values={form.asignado_ids.map(String)} onValuesChange={(values) => setForm({ ...form, asignado_ids: values.map(Number) })} options={people.map((person) => ({ value: String(person.id), label: person.nombre, keywords: person.username }))} placeholder="Seleccionar responsables..." searchPlaceholder="Escribe un nombre o usuario..." /></div>
          <div className="space-y-2"><Label>Etiquetas</Label><SearchableMultiSelect aria-label="Etiquetas" values={form.etiqueta_ids.map(String)} onValuesChange={(values) => setForm({ ...form, etiqueta_ids: values.map(Number) })} options={availableLabels.map((tag) => ({ value: String(tag.id), label: `${tag.nombre}${tag.is_active ? "" : " · retirada"}`, keywords: tag.color }))} placeholder="Seleccionar etiquetas..." searchPlaceholder="Escribe para filtrar etiquetas..." /></div>
          <div className="space-y-2"><Label htmlFor="reminder">Recordatorio interno</Label><SearchableSelect id="reminder" value={String(form.recordatorios[0]?.minutos_antes ?? -1)} onValueChange={(value) => setForm({ ...form, recordatorios: Number(value) < 0 ? [] : [{ minutos_antes: Number(value), canal: "interno" }] })} options={reminderOptions} searchPlaceholder="Buscar recordatorio..." /></div>
        </SheetSection>
      </SheetBody>
      <SheetFooter>{selected && manageable && <ConfirmActionDialog title="Eliminar evento" description={`Se eliminará “${selected.titulo}”. Esta acción no se puede deshacer.`} confirmLabel="Eliminar" destructive onConfirm={async () => { await calendarAPI.remove(selected.id); setOpen(false); await load(); toast.success("Evento eliminado"); }}><Button variant="destructive" className="mr-auto"><Trash2 />Eliminar</Button></ConfirmActionDialog>}<Button variant="outline" onClick={() => setOpen(false)}>Cancelar</Button>{editable && <Button disabled={saving} onClick={() => void save()}>{saving ? "Guardando..." : "Guardar"}</Button>}</SheetFooter>
    </SheetContent></Sheet>

    {events.map((event) => manageable && <ConfirmActionDialog key={event.id} title="Eliminar evento" description={`Se eliminará “${event.titulo}”. Esta acción no se puede deshacer.`} confirmLabel="Eliminar" destructive onConfirm={async () => { await calendarAPI.remove(event.id); await load(); toast.success("Evento eliminado"); }}><Button id={`calendar-delete-${event.id}`} type="button" className="hidden" aria-hidden="true" /></ConfirmActionDialog>)}
  </main>;
}
