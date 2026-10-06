import { useEffect, useMemo, useState, type DragEvent } from "react";
import { ChevronDown, ChevronRight, GripVertical, Pencil, Plus, Trash2 } from "lucide-react";
import { toast } from "sonner";

import { ActionButton } from "@/components/action-button";
import { ConfirmActionDialog } from "@/components/confirm-action-dialog";
import { ExcelDownloadButton } from "@/components/excel-download-button";
import { MenuGlyph } from "@/components/menu-icon";
import { ALL_MENU_ICON_NAMES, MENU_ICONS, menuIconExists } from "@/lib/menu-icons";
import { RecordContextMenu } from "@/components/record-context-menu";
import { RowActionsMenu } from "@/components/row-actions-menu";
import { SearchableSelect } from "@/components/searchable-select";
import { StandardListToolbar } from "@/components/standard-list-toolbar";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Sheet, SheetBody, SheetContent, SheetDescription, SheetFooter, SheetHeader, SheetSection, SheetSectionDescription, SheetSectionTitle, SheetTitle } from "@/components/ui/sheet";
import { Switch } from "@/components/ui/switch";
import { useAuth } from "@/context/AuthContext";
import { usePlatformSettings } from "@/context/PlatformSettingsContext";
import { wolverineAPI } from "@/features/wolverine/api";
import type { MenuNode } from "@/features/wolverine/types";
import { apiErrorMessage } from "@/lib/api-error";
import { downloadExcelXlsx, includesSearch } from "@/lib/table-tools";
import { useIncomingSearch } from "@/lib/use-incoming-search";
import { useDoubleClickPreference } from "@/lib/use-double-click-preference";

type MenuKind = MenuNode["tipo"];
type MenuRow = MenuNode & { depth: number; moduleId: number; moduleName: string };
type DropMode = "before" | "inside" | "after";
type DropTarget = { id: number; mode: DropMode } | null;
type MenuForm = { parent_id: number | null; nombre: string; slug: string; ruta: string; icono: string; orden: number; is_visible: boolean; is_active: boolean; tipo: MenuKind };
type MenuDoubleClick = "edit" | "none";
const MENU_DOUBLE_CLICK: readonly MenuDoubleClick[] = ["edit", "none"];
const FIXED_ROUTES: Record<string, string> = {
  "inicio": "/inicio",
  "medical-plans": "/plataforma/medical/plans",
  "medical-network": "/plataforma/medical/network",
  "medical-emissions": "/plataforma/medical/emissions",
  "medical-dispatches": "/plataforma/medical/dispatches",
  "medical-liquidations": "/plataforma/medical/liquidations",
  "medical-billing": "/plataforma/medical/billing",
  "medical-reports": "/plataforma/medical/reports",
  "usuarios": "/plataforma/administracion/usuarios",
  "roles": "/plataforma/administracion/roles",
  "accesos": "/plataforma/administracion/accesos",
  "menus": "/plataforma/sistema/menus",
  "auditoria": "/plataforma/sistema/auditoria",
  "calendario": "/plataforma/sistema/calendario",
  "notificaciones": "/plataforma/sistema/notificaciones",
  "documentacion": "/plataforma/sistema/documentacion",
  "devops": "/plataforma/sistema/devops",
  "configuracion": "/plataforma/sistema/configuracion",
  "general": "/plataforma/sistema/configuracion/general",
  "apariencia": "/plataforma/sistema/configuracion/apariencia",
  "smtp": "/plataforma/sistema/configuracion/smtp",
  "whatsapp": "/plataforma/sistema/configuracion/whatsapp",
  "plantillas": "/plataforma/sistema/configuracion/plantillas",
  "avi-configuracion": "/plataforma/automatizacion/avi",
  "documentos": "/documentos/archivos",
  "seccion-configuracion": "/plataforma/seccion/configuracion",
};

const emptyForm = (): MenuForm => ({ parent_id: null, nombre: "", slug: "", ruta: "", icono: "", orden: 0, is_visible: true, is_active: true, tipo: "modulo" });
const PROTECTED_SLUGS = new Set([...Object.keys(FIXED_ROUTES), "medical", "plataforma", "usuarios-seguridad", "sistema", "automatizacion", "modulo-documentos"]);
const normalizeIconSearch = (value: string) => value.normalize("NFD").replace(/\p{Diacritic}/gu, "").toLowerCase();
const kindLabel = (tipo: MenuKind) => ({ seccion: "Sección", modulo: "Módulo", menu: "Menú", submenu: "Submenú", pestana: "Pestaña" }[tipo]);
const rowTone = (tipo: MenuKind) => ({
  seccion: "bg-teal-50/80 dark:bg-teal-950/25",
  modulo: "bg-slate-50/80 dark:bg-slate-900/30",
  menu: "bg-sky-100/65 dark:bg-sky-950/30",
  submenu: "bg-amber-50/40 dark:bg-amber-950/10",
  pestana: "bg-violet-50/40 dark:bg-violet-950/10",
}[tipo]);
const badgeTone = (tipo: MenuKind) => ({
  seccion: "border-teal-300/80 bg-teal-100/80 text-teal-800 dark:border-teal-800 dark:bg-teal-950/40 dark:text-teal-200",
  modulo: "border-slate-300/70 bg-slate-100/70 text-slate-700 dark:border-slate-700 dark:bg-slate-900/50 dark:text-slate-300",
  menu: "border-sky-300/90 bg-sky-100/90 text-sky-800 dark:border-sky-800 dark:bg-sky-950/45 dark:text-sky-200",
  submenu: "border-amber-200/80 bg-amber-50/80 text-amber-700 dark:border-amber-900 dark:bg-amber-950/25 dark:text-amber-300",
  pestana: "border-violet-200/80 bg-violet-50/80 text-violet-700 dark:border-violet-900 dark:bg-violet-950/25 dark:text-violet-300",
}[tipo]);

function flatten(items: MenuNode[]): MenuRow[] {
  return items.flatMap((module) => {
    const visit = (item: MenuNode, depth: number): MenuRow[] => [
      { ...item, depth, moduleId: module.id, moduleName: module.nombre },
      ...item.children.flatMap((child) => visit(child, depth + 1)),
    ];
    return visit(module, 0);
  });
}

function routeFor(form: MenuForm, rows: MenuRow[]) {
  if (FIXED_ROUTES[form.slug]) return FIXED_ROUTES[form.slug];
  if (form.tipo === "modulo") return null;
  if (form.tipo === "seccion") {
    const parent = rows.find((row) => row.id === form.parent_id);
    return parent && form.slug ? `/${parent.slug}/seccion/${form.slug}` : "";
  }
  if (form.tipo === "menu" && form.slug === "inicio" && form.parent_id === null) return "/inicio";
  const parent = rows.find((row) => row.id === form.parent_id);
  if (!parent || !form.slug) return "";
  const parentRoute = parent.ruta ?? `/${parent.slug}`;
  return `${parentRoute}/${form.slug}`;
}

export default function MenusPanel() {
  const { can } = useAuth();
  const { settings } = usePlatformSettings();
  const [menus, setMenus] = useState<MenuNode[]>([]);
  const [editing, setEditing] = useState<number | null>(null);
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState<MenuForm>(emptyForm);
  const [search, setSearch] = useIncomingSearch();
  const [typeFilter, setTypeFilter] = useState("all");
  const [stateFilter, setStateFilter] = useState("all");
  const [draggedId, setDraggedId] = useState<number | null>(null);
  const [dropTarget, setDropTarget] = useState<DropTarget>(null);
  const [collapsed, setCollapsed] = useState<Set<number>>(new Set());
  const [iconSearch, setIconSearch] = useState("");
  const [doubleClickAction, setDoubleClickAction] = useDoubleClickPreference<MenuDoubleClick>("menus", MENU_DOUBLE_CLICK, can("menus", "editor") ? "edit" : "none");
  const rows = useMemo(() => flatten(menus), [menus]);
  const routePreview = routeFor(form, rows);
  const hasFixedRoute = editing !== null && PROTECTED_SLUGS.has(rows.find((row) => row.id === editing)?.slug ?? "");
  const parentOptions = rows.filter((row) => {
    if (form.tipo === "seccion") return row.tipo === "modulo" && row.parent_id === null;
    if (form.tipo === "modulo") return row.tipo === "seccion";
    if (form.tipo === "menu") return row.tipo === "modulo";
    if (form.tipo === "submenu") return row.tipo === "menu" && !row.children.some((child) => child.tipo === "pestana");
    if (form.tipo === "pestana") return row.tipo === "submenu" || (row.tipo === "menu" && !row.children.some((child) => child.tipo === "submenu"));
    return false;
  });
  const iconOptions = useMemo(() => {
    const term = normalizeIconSearch(iconSearch.trim());
    if (!term) return MENU_ICONS.map(({ name, label }) => ({ name, label }));
    const options = [
      ...MENU_ICONS.filter(({ name, label }) => normalizeIconSearch(`${name} ${label}`).includes(term)).map(({ name, label }) => ({ name, label })),
      ...ALL_MENU_ICON_NAMES.filter((name) => name.includes(term)).map((name) => ({ name, label: name })),
    ];
    return [...new Map(options.map((option) => [option.name, option])).values()].slice(0, 80);
  }, [iconSearch]);
  const visibleRows = useMemo(() => rows.filter((menu) => includesSearch([menu.nombre, menu.slug, menu.ruta, menu.icono, menu.moduleName, kindLabel(menu.tipo)], search)).filter((menu) => typeFilter === "all"
    || (typeFilter === "section" && menu.tipo === "seccion")
    || (typeFilter === "module" && menu.tipo === "modulo")
    || (typeFilter === "menu" && menu.tipo === "menu")
    || (typeFilter === "submenu" && menu.tipo === "submenu")
    || (typeFilter === "pestana" && menu.tipo === "pestana")).filter((menu) => stateFilter === "all"
      || (stateFilter === "active" && menu.is_active)
      || (stateFilter === "inactive" && !menu.is_active)).filter((menu) => {
      if (search) return true;
      let parentId = menu.parent_id;
      while (parentId) {
        if (collapsed.has(parentId)) return false;
        parentId = rows.find((row) => row.id === parentId)?.parent_id ?? null;
      }
      return true;
    }), [rows, search, typeFilter, stateFilter, collapsed]);

  const toggleCollapsed = (menuId: number) => setCollapsed((current) => {
    const next = new Set(current);
    if (next.has(menuId)) next.delete(menuId); else next.add(menuId);
    return next;
  });
  const load = () => wolverineAPI.menus().then(setMenus).catch((error) => toast.error(apiErrorMessage(error, "No se pudieron cargar los menús")));
  useEffect(() => { void load(); }, []);

  const openCreate = () => { setEditing(null); setForm(emptyForm()); setIconSearch(""); setShowForm(true); };
  const openEdit = (menu: MenuRow) => {
    setEditing(menu.id);
    setIconSearch("");
    setForm({ parent_id: menu.parent_id, nombre: menu.nombre, slug: menu.slug, ruta: menu.ruta ?? "", icono: menu.icono ?? "Circle", orden: menu.orden, is_visible: menu.is_visible, is_active: menu.is_active, tipo: menu.tipo });
    setShowForm(true);
  };
  const save = async () => {
    if (form.tipo !== "modulo" && !form.parent_id && form.slug !== "inicio") return toast.error("Selecciona la opción padre");
    try {
      await wolverineAPI.saveMenu({ ...form, icono: form.tipo === "menu" || form.tipo === "seccion" ? form.icono : null, ruta: routePreview }, editing ?? undefined);
      setEditing(null); setShowForm(false); setForm(emptyForm()); await load(); toast.success("Menú guardado");
    } catch (error) { toast.error(apiErrorMessage(error, "No se pudo guardar el menú")); }
  };
  const exportMenus = () => downloadExcelXlsx("menus", visibleRows, [
    { header: "Nivel", value: (menu) => kindLabel(menu.tipo) },
    { header: "Modulo", value: (menu) => menu.moduleName },
    { header: "Opcion", value: (menu) => menu.nombre },
    { header: "Slug", value: (menu) => menu.slug },
    { header: "Ruta", value: (menu) => menu.ruta },
    { header: "Icono", value: (menu) => menu.icono },
    { header: "Visible", value: (menu) => menu.is_visible ? "Si" : "No" },
    { header: "Activo", value: (menu) => menu.is_active ? "Si" : "No" },
  ], { organizationName: settings.organization_name, criteria: { Busqueda: search || "Sin busqueda", Jerarquia: typeFilter, Estado: stateFilter, Orden: "Jerarquia configurada", Registros: visibleRows.length } });

  const dragMode = (event: DragEvent<HTMLDivElement>, target: MenuRow): DropMode => {
    const ratio = (event.clientY - event.currentTarget.getBoundingClientRect().top) / event.currentTarget.getBoundingClientRect().height;
    if (ratio < 0.3) return "before";
    if (ratio > 0.7 || target.tipo === "pestana") return "after";
    return "inside";
  };
  const move = async (target: MenuRow, mode: DropMode) => {
    if (!draggedId || draggedId === target.id) return;
    const dragged = rows.find((row) => row.id === draggedId);
    if (!dragged) return;
    const descendantIds = new Set(rows.filter((row) => {
      let parentId = row.parent_id;
      while (parentId) {
        if (parentId === dragged.id) return true;
        parentId = rows.find((item) => item.id === parentId)?.parent_id ?? null;
      }
      return false;
    }).map((row) => row.id));
    if (descendantIds.has(target.id)) return toast.error("No puedes mover una opción dentro de sus descendientes");
    const parentId = mode === "inside" ? target.id : target.parent_id;
    const parent = rows.find((row) => row.id === parentId);
    const allowed = dragged.tipo === "seccion" ? parent?.tipo === "modulo" && parent.parent_id === null
      : dragged.tipo === "modulo" ? parentId === null || parent?.tipo === "seccion"
      : dragged.tipo === "menu" ? parent?.tipo === "modulo"
      : dragged.tipo === "submenu" ? parent?.tipo === "menu" && !parent.children.some((child) => child.id !== dragged.id && child.tipo === "pestana")
      : parent?.tipo === "submenu" || (parent?.tipo === "menu" && !parent.children.some((child) => child.id !== dragged.id && child.tipo === "submenu"));
    if (!allowed) return toast.error("Ese destino no admite este tipo de opción");
    const siblings = rows.filter((row) => row.parent_id === parentId && row.id !== dragged.id);
    const targetIndex = mode === "inside" ? siblings.length : siblings.findIndex((row) => row.id === target.id);
    const position = mode === "after" ? targetIndex + 1 : targetIndex;
    try {
      await wolverineAPI.moveMenu(dragged.id, { parent_id: parentId, position: Math.max(0, position) });
      await load(); toast.success("Orden del menú actualizado");
    } catch (error) { toast.error(apiErrorMessage(error, "No se pudo mover la opción")); }
    finally { setDraggedId(null); setDropTarget(null); }
  };

  return <main className="space-y-5 p-5 md:p-7">
    <div className="flex flex-wrap items-center justify-between gap-3"><div><h1 className="text-2xl font-semibold">Menús configurables</h1><p className="text-sm text-muted-foreground">Arrastra para ordenar o cambiar de padre. El doble clic es configurable y el clic derecho conserva todas las opciones.</p></div><div className="flex flex-wrap items-center gap-2">{can("menus", "editor") && <ActionButton tone="new" onClick={openCreate}><Plus className="size-4" />Nueva opción</ActionButton>}<ExcelDownloadButton onDownload={exportMenus} disabled={visibleRows.length === 0} /></div></div>
    <Sheet open={showForm} onOpenChange={setShowForm}><SheetContent className="w-full sm:max-w-2xl"><SheetHeader><SheetTitle>{editing ? "Editar opción" : "Nueva opción"}</SheetTitle><SheetDescription>La ruta y la posición se gestionan automáticamente desde la jerarquía.</SheetDescription></SheetHeader>{can("menus", "editor") && <SheetBody className="space-y-7">
      <SheetSection><div><SheetSectionTitle>Ubicación e identidad</SheetSectionTitle><SheetSectionDescription>Jerarquía principal: Módulo → Menú. Una sección se abre desde un módulo principal y contiene sus propios módulos, menús, submenús y pestañas.</SheetSectionDescription></div><div className="grid gap-x-5 gap-y-5 sm:grid-cols-2">
        <div className="space-y-2"><Label>Nivel</Label><SearchableSelect disabled={editing !== null} value={form.tipo} onValueChange={(value) => setForm({ ...form, tipo: value as MenuKind, parent_id: null, icono: value === "menu" || value === "seccion" ? "Menu" : "" })} options={[{ value: "seccion", label: "Sección" }, { value: "modulo", label: "Módulo" }, { value: "menu", label: "Menú" }, { value: "submenu", label: "Submenú" }, { value: "pestana", label: "Pestaña" }]} searchPlaceholder="Buscar nivel..." /></div>
        {form.slug !== "inicio" && <div className="space-y-2"><Label>Opción padre</Label><SearchableSelect disabled={editing !== null} value={form.parent_id ? String(form.parent_id) : ""} onValueChange={(value) => setForm({ ...form, parent_id: value ? Number(value) : null })} options={[...(form.tipo === "modulo" ? [{ value: "", label: "Raíz del menú principal" }] : []), ...parentOptions.map((row) => ({ value: String(row.id), label: `${row.tipo !== "modulo" ? `${row.moduleName} / ` : ""}${row.nombre} (${kindLabel(row.tipo)})`, keywords: `${row.slug} ${row.ruta ?? ""}` }))]} placeholder={form.tipo === "modulo" ? "Raíz del menú principal" : "Seleccionar..."} searchPlaceholder="Escribe para filtrar opciones..." /></div>}
        <div className="space-y-2"><Label>Nombre</Label><Input value={form.nombre} onChange={(event) => setForm({ ...form, nombre: event.target.value })} /></div>
        <div className="space-y-2"><Label>Slug en espanol, sin tildes</Label><Input disabled={hasFixedRoute} value={form.slug} onChange={(event) => setForm({ ...form, slug: event.target.value.toLowerCase().replace(/[^a-z0-9._-]/g, "-") })} />{hasFixedRoute && <p className="text-xs text-muted-foreground">Identificador protegido porque está vinculado a una pantalla implementada.</p>}</div>
        <div className="space-y-2 sm:col-span-2"><Label>Ruta generada</Label><Input readOnly value={routePreview ?? "Los modulos no tienen ruta"} className="font-mono text-xs" /></div>
      </div></SheetSection>
      {(form.tipo === "menu" || form.tipo === "seccion") && <SheetSection><div><SheetSectionTitle>Icono de la opción</SheetSectionTitle><SheetSectionDescription>Busca cualquier icono de Lucide o escribe directamente su nombre. Se carga bajo demanda y el color se asigna automáticamente.</SheetSectionDescription></div><div className="space-y-4"><div className="space-y-2"><Label htmlFor="menu-icon-search">Buscar iconos</Label><Input id="menu-icon-search" value={iconSearch} onChange={(event) => setIconSearch(event.target.value)} placeholder="Ejemplo: usuario, archivo, vehículo, salud..." /></div><div className="space-y-2"><Label htmlFor="menu-icon-name">Nombre libre del icono</Label><div className="flex items-center gap-3"><Input id="menu-icon-name" value={form.icono} maxLength={60} onChange={(event) => setForm({ ...form, icono: event.target.value })} placeholder="Ejemplo: ambulance o Ambulance" /><span className="flex size-10 shrink-0 items-center justify-center rounded-lg border bg-muted/30"><MenuGlyph name={form.icono} className="size-5" /></span></div>{form.icono && !menuIconExists(form.icono) && <p className="text-xs text-destructive">No existe un icono Lucide con ese nombre.</p>}</div><div className="grid max-h-64 grid-cols-5 gap-2 overflow-y-auto pr-1 sm:grid-cols-8">{iconOptions.map(({ name, label }) => <button key={name} type="button" title={label} aria-label={label} onClick={() => setForm({ ...form, icono: name })} className={`flex h-12 items-center justify-center rounded-xl border transition ${form.icono === name ? "border-primary bg-primary/10 ring-2 ring-primary/25" : "bg-background hover:bg-muted"}`}><MenuGlyph name={name} className="size-5" /></button>)}</div>{iconSearch && !iconOptions.length && <p className="text-sm text-muted-foreground">No se encontraron iconos con ese criterio.</p>}</div>
      </SheetSection>}
      <SheetSection><div><SheetSectionTitle>Disponibilidad</SheetSectionTitle><SheetSectionDescription>Controla si la opción aparece y puede utilizarse.</SheetSectionDescription></div><div className="grid gap-3 sm:grid-cols-2"><label className="flex items-center justify-between gap-4 rounded-xl border bg-muted/20 px-4 py-3.5 text-sm font-medium"><span>Visible</span><Switch checked={form.is_visible} onCheckedChange={(value) => setForm({ ...form, is_visible: value })} /></label><label className="flex items-center justify-between gap-4 rounded-xl border bg-muted/20 px-4 py-3.5 text-sm font-medium"><span>Activa</span><Switch checked={form.is_active} onCheckedChange={(value) => setForm({ ...form, is_active: value })} /></label></div></SheetSection>
    </SheetBody>}<SheetFooter><Button variant="outline" onClick={() => setShowForm(false)}>Cancelar</Button><ActionButton tone={editing ? "edit" : "new"} onClick={save} disabled={form.nombre.trim().length < 2 || form.slug.length < 2 || (form.tipo !== "modulo" && !form.parent_id && form.slug !== "inicio") || ((form.tipo === "menu" || form.tipo === "seccion") && !menuIconExists(form.icono))}>{editing ? "Actualizar" : "Crear"}</ActionButton></SheetFooter></SheetContent></Sheet>
    <Card className="gap-0 border-border/70 py-0 shadow-none"><CardContent className="space-y-3 p-4 md:p-5">
      <StandardListToolbar embedded filterLabel="Jerarquía" filterControls={<div className="flex items-center gap-2"><Label htmlFor="menu-state-filter" className="text-[11px] font-medium text-muted-foreground">Estado</Label><SearchableSelect id="menu-state-filter" className="h-8 min-w-40 text-xs" value={stateFilter} onValueChange={setStateFilter} options={[{ value: "all", label: "Todos los estados" }, { value: "active", label: "Activos" }, { value: "inactive", label: "Inactivos" }]} searchPlaceholder="Buscar estado..." /></div>} resultLabel={`${visibleRows.length} opción${visibleRows.length === 1 ? "" : "es"} encontrada${visibleRows.length === 1 ? "" : "s"}`} search={search} onSearchChange={setSearch} searchPlaceholder="Buscar módulo, menú, submenú, pestaña, slug, ruta o icono..." filters={[
      { value: "all", label: "Todos", count: rows.length },
      { value: "section", label: "Secciones", count: rows.filter((row) => row.tipo === "seccion").length, className: badgeTone("seccion"), activeClassName: "ring-1 ring-teal-300 dark:ring-teal-800" },
      { value: "module", label: "Módulos", count: rows.filter((row) => row.tipo === "modulo").length, className: badgeTone("modulo"), activeClassName: "ring-1 ring-slate-300 dark:ring-slate-700" },
      { value: "menu", label: "Menús", count: rows.filter((row) => row.tipo === "menu").length, className: badgeTone("menu"), activeClassName: "ring-1 ring-sky-300 dark:ring-sky-800" },
      { value: "submenu", label: "Submenús", count: rows.filter((row) => row.tipo === "submenu").length, className: badgeTone("submenu"), activeClassName: "ring-1 ring-amber-300 dark:ring-amber-800" },
      { value: "pestana", label: "Pestañas", count: rows.filter((row) => row.tipo === "pestana").length, className: badgeTone("pestana"), activeClassName: "ring-1 ring-violet-300 dark:ring-violet-800" },
    ]} activeFilter={typeFilter} onFilterChange={setTypeFilter} resultCount={visibleRows.length} totalCount={rows.length} />
      <div className="space-y-1">{visibleRows.map((menu) => { const doubleClickChoices = [...(can("menus", "editor") ? [{ value: "edit" as const, label: "Editar" }] : []), { value: "none" as const, label: "Ninguna acción" }]; return <RecordContextMenu key={menu.id} actions={[{ label: "Editar", icon: Pencil, disabled: !can("menus", "editor"), onSelect: () => openEdit(menu) }, { label: "Eliminar...", icon: Trash2, destructive: true, disabled: !can("menus", "gestor"), onSelect: () => document.getElementById(`menu-delete-${menu.id}`)?.click() }]} doubleClick={{ value: doubleClickAction, onChange: setDoubleClickAction, choices: doubleClickChoices }}><div draggable={menu.slug !== "inicio" && can("menus", "editor")} title={`Doble clic: ${doubleClickAction === "edit" ? "editar" : "sin acción"}`} onDragStart={(event) => { if ((event.target as Element).closest("[data-no-drag]")) { event.preventDefault(); return; } setDraggedId(menu.id); }} onDragEnd={() => { setDraggedId(null); setDropTarget(null); }} onDragOver={(event) => { if (!draggedId) return; event.preventDefault(); setDropTarget({ id: menu.id, mode: dragMode(event, menu) }); }} onDrop={(event) => { event.preventDefault(); void move(menu, dropTarget?.id === menu.id ? dropTarget.mode : "after"); }} onDoubleClick={() => doubleClickAction === "edit" && can("menus", "editor") && openEdit(menu)} style={{ marginLeft: `${menu.depth * 20}px` }} className={`group relative flex min-h-12 items-center gap-2 rounded-md border border-border/70 px-2 py-2 transition-colors hover:border-border hover:brightness-[0.985] dark:hover:brightness-110 ${menu.slug === "inicio" ? "" : "cursor-grab active:cursor-grabbing"} ${rowTone(menu.tipo)} ${draggedId === menu.id ? "opacity-40" : ""} ${dropTarget?.id === menu.id ? dropTarget.mode === "inside" ? "ring-1 ring-primary" : dropTarget.mode === "before" ? "border-t-2 border-t-primary" : "border-b-2 border-b-primary" : ""}`}>
        {can("menus", "editor") && menu.slug !== "inicio" && <GripVertical className="size-3.5 shrink-0 cursor-grab text-muted-foreground/55 active:cursor-grabbing" />}{menu.children.length ? <Button data-no-drag type="button" variant="ghost" size="icon" className="size-7 shrink-0 text-muted-foreground" title={collapsed.has(menu.id) ? "Desplegar rama" : "Resumir rama"} onClick={(event) => { event.stopPropagation(); toggleCollapsed(menu.id); }} onDoubleClick={(event) => event.stopPropagation()}>{collapsed.has(menu.id) ? <ChevronRight className="size-3.5" /> : <ChevronDown className="size-3.5" />}</Button> : <span className="size-7 shrink-0" />}{menu.tipo === "menu" && <span className="flex size-6 shrink-0 items-center justify-center text-muted-foreground"><MenuGlyph name={menu.icono} className="size-3.5" /></span>}<div className="min-w-0 flex-1"><div className="flex flex-wrap items-center gap-2"><span className={menu.tipo === "modulo" ? "text-sm font-semibold uppercase tracking-[0.08em]" : "text-sm font-medium"}>{menu.nombre}</span><Badge variant="outline" className={`h-5 px-1.5 text-[10px] font-normal ${badgeTone(menu.tipo)}`}>{kindLabel(menu.tipo)}</Badge>{!menu.is_active && <Badge variant="destructive" className="h-5 px-1.5 text-[10px] font-normal">Inactivo</Badge>}{!menu.is_visible && <Badge variant="outline" className="h-5 px-1.5 text-[10px] font-normal text-muted-foreground">Oculto</Badge>}</div><p className="truncate text-[11px] text-muted-foreground/75"><span className="font-mono">{menu.slug}</span>{menu.ruta ? ` · ${menu.ruta}` : " · contenedor sin ruta"}</p></div>
        <div data-no-drag className="flex shrink-0 gap-1.5" onDoubleClick={(event) => event.stopPropagation()}><RowActionsMenu label={menu.nombre} actions={[{ label: "Editar", icon: Pencil, hidden: !can("menus", "editor"), onSelect: () => openEdit(menu) }, { label: "Eliminar...", icon: Trash2, destructive: true, hidden: !can("menus", "gestor"), onSelect: () => document.getElementById(`menu-delete-${menu.id}`)?.click() }]} doubleClick={{ value: doubleClickAction, onChange: setDoubleClickAction, choices: doubleClickChoices }} />{can("menus", "gestor") && <ConfirmActionDialog title="Eliminar opción" description={`Se eliminará ${menu.nombre} y todos sus descendientes.`} confirmLabel="Eliminar" destructive onConfirm={async () => { try { await wolverineAPI.deleteMenu(menu.id); await load(); toast.success("Opción eliminada"); } catch (error) { toast.error(apiErrorMessage(error, "No se pudo eliminar la opción")); throw error; } }}><button id={`menu-delete-${menu.id}`} type="button" className="hidden" aria-hidden="true" /></ConfirmActionDialog>}</div>
      </div></RecordContextMenu>; })}</div>
      {visibleRows.length === 0 && <p className="rounded-xl border border-dashed p-8 text-center text-sm text-muted-foreground">No hay opciones para los filtros actuales.</p>}
    </CardContent></Card>
  </main>;
}
