import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { ArrowLeft, ShieldCheck } from "lucide-react";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";

import { ExcelDownloadButton } from "@/components/excel-download-button";
import { MenuIcon } from "@/components/menu-icon";
import { SearchableSelect } from "@/components/searchable-select";
import { StandardListToolbar } from "@/components/standard-list-toolbar";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Switch } from "@/components/ui/switch";
import { useAuth } from "@/context/AuthContext";
import { usePlatformSettings } from "@/context/PlatformSettingsContext";
import { wolverineAPI } from "@/features/wolverine/api";
import type { AccessGrant, AccessLevel, MenuNode, Role, User } from "@/features/wolverine/types";
import { apiErrorMessage } from "@/lib/api-error";
import { fromLimaInput, toLimaInput } from "@/lib/dates";
import { downloadExcelXlsx, includesSearch } from "@/lib/table-tools";
import { useIncomingSearch } from "@/lib/use-incoming-search";

type Draft = Pick<AccessGrant, "access_level" | "starts_at" | "ends_at" | "is_active"> & { is_temporary: boolean };
type MenuRow = MenuNode & { depth: number; moduleId: number; moduleName: string };

const emptyDraft = (): Draft => ({ access_level: "none", starts_at: null, ends_at: null, is_active: true, is_temporary: false });
const draftsFromGrants = (grants: AccessGrant[]) => Object.fromEntries(grants.map((grant) => [grant.menu_id, { access_level: grant.access_level, starts_at: grant.starts_at, ends_at: grant.ends_at, is_active: grant.is_active, is_temporary: Boolean(grant.starts_at || grant.ends_at) }]));
const levelLabel = (tipo: MenuNode["tipo"]) => ({ seccion: "Sección", modulo: "Módulo", menu: "Menú", submenu: "Submenú", pestana: "Pestaña" }[tipo]);
function flatten(items: MenuNode[]): MenuRow[] {
  const visit = (item: MenuNode, depth: number, inheritedModule?: MenuNode): MenuRow[] => {
    const module = item.tipo === "modulo" ? item : inheritedModule ?? item;
    return [
      { ...item, depth, moduleId: module.id, moduleName: module.nombre },
      ...item.children.flatMap((child) => visit(child, depth + 1, module)),
    ];
  };
  return items.flatMap((item) => visit(item, 0));
}
function isWithinMenu(menu: MenuRow, menuId: number, rows: MenuRow[]) {
  let current: MenuRow | undefined = menu;
  while (current) {
    if (current.id === menuId) return true;
    current = rows.find((row) => row.id === current?.parent_id);
  }
  return false;
}

function hasActiveSuperiorRole(user: User) {
  const now = Date.now();
  return user.is_active && user.role_assignments.some((assignment) => {
    if (!assignment.is_active || !assignment.rol.is_active || !assignment.rol.es_superusuario) return false;
    if (assignment.is_permanent) return true;
    const startsAt = assignment.starts_at ? Date.parse(assignment.starts_at) : Number.NaN;
    const endsAt = assignment.ends_at ? Date.parse(assignment.ends_at) : Number.NaN;
    return Number.isFinite(startsAt) && Number.isFinite(endsAt) && startsAt <= now && now < endsAt;
  });
}

export default function AccessPanel() {
  const navigate = useNavigate();
  const { can } = useAuth();
  const { settings } = usePlatformSettings();
  const [roles, setRoles] = useState<Role[]>([]);
  const [users, setUsers] = useState<User[]>([]);
  const [menus, setMenus] = useState<MenuNode[]>([]);
  const [kind, setKind] = useState<"role" | "user">("role");
  const [subjectId, setSubjectId] = useState<number | null>(null);
  const [drafts, setDrafts] = useState<Record<number, Draft>>({});
  const [search, setSearch] = useIncomingSearch();
  const [quickFilter, setQuickFilter] = useState("all");
  const [moduleFilter, setModuleFilter] = useState("all");
  const [menuFilter, setMenuFilter] = useState("all");
  const [stateFilter, setStateFilter] = useState("all");
  const [validityFilter, setValidityFilter] = useState("all");
  const usersCache = useRef<User[] | null>(null);
  const usersRequest = useRef<Promise<User[]> | null>(null);
  const saveTimers = useRef(new Map<number, number>());
  const saveVersions = useRef(new Map<number, number>());
  const rows = useMemo(() => flatten(menus).filter((menu) => menu.tipo !== "seccion"), [menus]);
  const moduleGroups = useMemo(() => [...new Map(rows.map((row) => [
    row.moduleId,
    { id: row.moduleId, nombre: row.moduleName },
  ])).values()], [rows]);
  const selectedRole = kind === "role" ? roles.find((role) => role.id === subjectId) : undefined;
  const selectedUser = kind === "user" ? users.find((user) => user.id === subjectId) : undefined;
  const unrestricted = Boolean((selectedRole?.is_active && selectedRole.es_superusuario) || (selectedUser && hasActiveSuperiorRole(selectedUser)));
  const canEditAccess = can("accesos", "editor");

  const ensureUsers = useCallback(async () => {
    if (usersCache.current) return usersCache.current;
    usersRequest.current ??= wolverineAPI.users();
    try {
      const rows = await usersRequest.current;
      usersCache.current = rows;
      setUsers(rows);
      return rows;
    } catch (error) {
      usersRequest.current = null;
      throw error;
    }
  }, []);

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const requestedSubjectId = Number(params.get("id"));
    const requestsUser = params.get("tipo") === "usuario";
    Promise.all([wolverineAPI.roles(), wolverineAPI.menus(), requestsUser ? ensureUsers() : Promise.resolve([])]).then(([roleRows, menuRows, userRows]) => {
      setRoles(roleRows); setMenus(menuRows);
      if (requestsUser && userRows.some((user) => user.id === requestedSubjectId)) {
        setKind("user");
        setSubjectId(requestedSubjectId);
      } else if (!requestsUser && roleRows.some((role) => role.id === requestedSubjectId)) {
        setKind("role");
        setSubjectId(requestedSubjectId);
      }
    }).catch(() => toast.error("No se pudo cargar la configuracion de accesos"));
  }, [ensureUsers]);
  useEffect(() => {
    if (!subjectId || unrestricted) { setDrafts({}); return; }
    let cancelled = false;
    const params = kind === "role" ? { role_id: subjectId } : { usuario_id: subjectId };
    wolverineAPI.grants(params).then((grants) => {
      if (!cancelled) setDrafts(draftsFromGrants(grants));
    }).catch(() => { if (!cancelled) toast.error("No se pudieron cargar los accesos"); });
    return () => { cancelled = true; };
  }, [kind, subjectId, unrestricted]);
  useEffect(() => () => {
    saveTimers.current.forEach((timer) => window.clearTimeout(timer));
    saveTimers.current.clear();
  }, [kind, subjectId]);

  const updateAndSave = (menuId: number, values: Partial<Draft>) => {
    const next = { ...(drafts[menuId] ?? emptyDraft()), ...values };
    setDrafts((current) => ({ ...current, [menuId]: next }));
    const previousTimer = saveTimers.current.get(menuId);
    if (previousTimer) window.clearTimeout(previousTimer);
    const version = (saveVersions.current.get(menuId) ?? 0) + 1;
    saveVersions.current.set(menuId, version);
    if (!canEditAccess || (next.is_temporary && (!next.starts_at || !next.ends_at))) return;
    saveTimers.current.set(menuId, window.setTimeout(() => {
      saveTimers.current.delete(menuId);
      void save(menuId, next, version);
    }, 300));
  };
  const save = async (menuId: number, draft: Draft, version: number) => {
    if (!subjectId) return;
    const savedKind = kind;
    const savedSubjectId = subjectId;
    const { is_temporary: isTemporary, ...values } = draft;
    try {
      await wolverineAPI.saveGrant({ role_id: savedKind === "role" ? savedSubjectId : null, usuario_id: savedKind === "user" ? savedSubjectId : null, menu_id: menuId, ...values, starts_at: isTemporary ? values.starts_at : null, ends_at: isTemporary ? values.ends_at : null });
      const params = savedKind === "role" ? { role_id: savedSubjectId } : { usuario_id: savedSubjectId };
      const refreshed = await wolverineAPI.grants(params);
      if (saveVersions.current.get(menuId) !== version || savedKind !== kind || savedSubjectId !== subjectId) return;
      setDrafts(draftsFromGrants(refreshed));
      toast.success(values.access_level === "none" ? "Acceso retirado de toda la rama" : "Cambio guardado automáticamente");
    } catch (error) { toast.error(apiErrorMessage(error, "No se pudo guardar el acceso")); }
  };
  const visibleRows = useMemo(() => rows.filter((menu) => {
    const draft = drafts[menu.id] ?? emptyDraft();
    const granted = unrestricted || draft.access_level !== "none";
    const active = menu.is_active && (unrestricted || draft.is_active);
    return includesSearch([menu.nombre, menu.slug, menu.ruta, menu.moduleName, levelLabel(menu.tipo), unrestricted ? "gestor sin restricciones" : draft.access_level], search)
      && (moduleFilter === "all" || String(menu.moduleId) === moduleFilter)
      && (menuFilter === "all" || isWithinMenu(menu, Number(menuFilter), rows))
      && (quickFilter === "all" || (quickFilter === "granted" && granted) || (quickFilter === "none" && !granted))
      && (stateFilter === "all" || (stateFilter === "active" && active) || (stateFilter === "inactive" && !active))
      && (validityFilter === "all" || (validityFilter === "permanent" && !draft.is_temporary) || (validityFilter === "temporary" && draft.is_temporary));
  }), [rows, drafts, unrestricted, search, moduleFilter, menuFilter, quickFilter, stateFilter, validityFilter]);
  const groups = moduleGroups.map((module) => ({ module, rows: visibleRows.filter((row) => row.moduleId === module.id) })).filter((group) => group.rows.length);
  const count = (filter: "granted" | "none") => rows.filter((menu) => filter === "granted" ? unrestricted || (drafts[menu.id]?.access_level ?? "none") !== "none" : !unrestricted && (drafts[menu.id]?.access_level ?? "none") === "none").length;
  const exportAccess = () => downloadExcelXlsx("accesos", visibleRows, [
    { header: "Modulo", value: (menu) => menu.moduleName },
    { header: "Nivel", value: (menu) => levelLabel(menu.tipo) },
    { header: "Opcion", value: (menu) => menu.nombre },
    { header: "Ruta", value: (menu) => menu.ruta },
    { header: "Acceso", value: (menu) => unrestricted ? "gestor" : drafts[menu.id]?.access_level ?? "none" },
    { header: "Vigencia", value: (menu) => unrestricted ? "Sin restriccion" : drafts[menu.id]?.is_temporary ? "Temporal" : "Permanente" },
    { header: "Desde", value: (menu) => unrestricted ? null : drafts[menu.id]?.starts_at },
    { header: "Hasta", value: (menu) => unrestricted ? null : drafts[menu.id]?.ends_at },
    { header: "Activo", value: (menu) => menu.is_active && (unrestricted || drafts[menu.id]?.is_active !== false) ? "Si" : "No" },
  ], { organizationName: settings.organization_name, criteria: { Sujeto: kind === "role" ? selectedRole?.nombre : selectedUser ? `${selectedUser.nombre} ${selectedUser.apellido}` : "Sin seleccionar", Busqueda: search || "Sin busqueda", Modulo: moduleFilter === "all" ? "Todos" : moduleGroups.find((module) => String(module.id) === moduleFilter)?.nombre, Menu: menuFilter === "all" ? "Todos" : rows.find((menu) => String(menu.id) === menuFilter)?.nombre, Acceso: quickFilter, Estado: stateFilter, Vigencia: validityFilter, Registros: visibleRows.length } });
  const resetFilters = () => { setQuickFilter("all"); setModuleFilter("all"); setMenuFilter("all"); setStateFilter("all"); setValidityFilter("all"); };
  const changeKind = (nextKind: "role" | "user") => {
    setKind(nextKind);
    setSubjectId(null);
    resetFilters();
    if (nextKind === "user") void ensureUsers().catch(() => toast.error("No se pudieron cargar los usuarios"));
  };
  const subjects = kind === "role" ? roles : users;
  const menuOptions = rows.filter((menu) => menu.tipo === "menu" && (moduleFilter === "all" || String(menu.moduleId) === moduleFilter));
  const openedFromUsers = new URLSearchParams(window.location.search).get("origen") === "usuarios";

  return <main className="space-y-5 p-5 md:p-7">
    <div className="flex flex-wrap items-center justify-between gap-3"><div><h1 className="text-2xl font-semibold">Accesos</h1><p className="text-sm text-muted-foreground">Permisos por rol o usuario en la estructura de ABISSOL.</p></div><div className="flex flex-wrap items-center gap-2">{openedFromUsers && <Button type="button" variant="outline" onClick={() => navigate("/plataforma/administracion/usuarios")}><ArrowLeft className="size-4" />Volver a usuarios</Button>}{subjectId && <ExcelDownloadButton onDownload={exportAccess} disabled={!visibleRows.length} />}</div></div>
    <Card className="gap-0 py-0"><CardContent className="flex flex-col gap-3 p-4 sm:flex-row sm:items-center sm:flex-nowrap md:p-5"><SearchableSelect aria-label="Tipo de sujeto" className="sm:w-44" value={kind} onValueChange={(value) => changeKind(value as "role" | "user")} options={[{ value: "role", label: "Por rol" }, { value: "user", label: "Por usuario" }]} searchPlaceholder="Buscar tipo..." /><SearchableSelect aria-label={kind === "role" ? "Rol" : "Usuario"} className="min-w-0 flex-1" value={subjectId ? String(subjectId) : ""} onValueChange={(value) => { setSubjectId(value ? Number(value) : null); resetFilters(); }} options={subjects.map((subject) => ({ value: String(subject.id), label: `${subject.nombre}${kind === "user" && "apellido" in subject ? ` ${subject.apellido}` : ""}`, keywords: "username" in subject ? `${subject.username} ${subject.correo}` : "" }))} placeholder={`Selecciona ${kind === "role" ? "un rol" : "un usuario"}`} searchPlaceholder={`Buscar ${kind === "role" ? "rol" : "usuario"}...`} /></CardContent></Card>
    {subjectId && <Card className="gap-0 py-0"><CardContent className="space-y-4 p-4 md:p-5">
      {unrestricted && <div className="flex items-start gap-3 rounded-xl border border-emerald-200 bg-emerald-50 p-4 text-emerald-900 dark:border-emerald-900 dark:bg-emerald-950/40 dark:text-emerald-100"><ShieldCheck className="mt-0.5 size-5 shrink-0" /><div><p className="font-semibold">Acceso total sin restricciones</p><p className="text-sm opacity-80">{kind === "role" ? "Este rol superior" : "Este usuario tiene activo un rol superior"} dispone de nivel Gestor en toda la estructura.</p></div></div>}
      <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4"><SearchableSelect value={moduleFilter} onValueChange={(value) => { setModuleFilter(value); setMenuFilter("all"); }} options={[{ value: "all", label: "Todos los módulos" }, ...moduleGroups.map((module) => ({ value: String(module.id), label: module.nombre }))]} searchPlaceholder="Buscar módulo..." /><SearchableSelect value={menuFilter} onValueChange={setMenuFilter} options={[{ value: "all", label: "Todos los menús" }, ...menuOptions.map((menu) => ({ value: String(menu.id), label: menu.nombre }))]} searchPlaceholder="Buscar menú..." /><SearchableSelect value={stateFilter} onValueChange={setStateFilter} options={[{ value: "all", label: "Todos los estados" }, { value: "active", label: "Activos" }, { value: "inactive", label: "Inactivos" }]} searchPlaceholder="Buscar estado..." /><SearchableSelect value={validityFilter} onValueChange={setValidityFilter} options={[{ value: "all", label: "Todas las vigencias" }, { value: "permanent", label: "Permanentes" }, { value: "temporary", label: "Temporales" }]} searchPlaceholder="Buscar vigencia..." /></div>
      <StandardListToolbar embedded resultLabel={`${visibleRows.length} opcion${visibleRows.length === 1 ? "" : "es"} encontrada${visibleRows.length === 1 ? "" : "s"}`} search={search} onSearchChange={setSearch} searchPlaceholder="Buscar módulo, menú, submenú, pestaña, ruta o nivel..." filters={[{ value: "all", label: "Todos", count: rows.length }, { value: "granted", label: "Con acceso", count: count("granted") }, { value: "none", label: "Sin acceso", count: count("none") }]} activeFilter={quickFilter} onFilterChange={setQuickFilter} resultCount={visibleRows.length} totalCount={rows.length} />
      {canEditAccess && !unrestricted && <p className="text-xs text-muted-foreground">Los cambios válidos se guardan automáticamente.</p>}
      <div className="space-y-5">{groups.map(({ module, rows: moduleRows }) => <section key={module.id} className="overflow-hidden rounded-xl border"><div className="border-b bg-muted/60 px-4 py-3"><div className="flex items-center gap-2"><span className="font-bold uppercase tracking-wide">{module.nombre}</span><Badge>Módulo</Badge></div><p className="text-xs text-muted-foreground">{moduleRows.length} opciones visibles</p></div><div className="divide-y">{moduleRows.map((menu) => {
        const draft = drafts[menu.id] ?? emptyDraft();
        return <div key={menu.id} className={`grid gap-3 p-4 lg:grid-cols-[minmax(190px,1.3fr)_130px_130px_minmax(165px,1fr)_minmax(165px,1fr)_90px] lg:items-center ${menu.tipo === "modulo" ? "bg-muted/25" : menu.tipo === "menu" ? "bg-background" : menu.tipo === "submenu" ? "bg-muted/10" : "bg-muted/5"}`} style={{ paddingLeft: `${16 + menu.depth * 24}px` }}><div className="flex min-w-0 items-center gap-2">{menu.tipo === "menu" && <MenuIcon name={menu.icono} seed={menu.slug} />}<div className="min-w-0"><div className="flex items-center gap-2"><span className={menu.tipo === "modulo" ? "font-bold" : "font-medium"}>{menu.tipo === "modulo" ? "Acceso al módulo" : menu.nombre}</span><Badge variant={menu.tipo === "submenu" || menu.tipo === "pestana" ? "outline" : "secondary"}>{levelLabel(menu.tipo)}</Badge></div><p className="truncate text-xs text-muted-foreground">{menu.ruta ?? menu.slug}</p></div></div>
          <div>{unrestricted ? <strong className="text-emerald-700 dark:text-emerald-300">Gestor</strong> : <SearchableSelect disabled={!canEditAccess} className="h-9" value={draft.access_level} onValueChange={(value) => updateAndSave(menu.id, { access_level: value as AccessLevel })} options={[{ value: "none", label: "Sin acceso" }, { value: "lector", label: "Lector" }, { value: "editor", label: "Editor" }, { value: "gestor", label: "Gestor" }]} searchPlaceholder="Buscar nivel..." />}</div>
          <div>{unrestricted ? <span className="text-sm text-muted-foreground">Sin restricción</span> : <SearchableSelect disabled={!canEditAccess} className="h-9" value={draft.is_temporary ? "temporary" : "permanent"} onValueChange={(value) => updateAndSave(menu.id, value === "temporary" ? { is_temporary: true } : { is_temporary: false, starts_at: null, ends_at: null })} options={[{ value: "permanent", label: "Permanente" }, { value: "temporary", label: "Temporal" }]} searchPlaceholder="Buscar vigencia..." />}</div>
          <div>{!unrestricted && draft.is_temporary ? <Input disabled={!canEditAccess} aria-label={`Desde ${menu.nombre}`} type="datetime-local" value={toLimaInput(draft.starts_at)} onChange={(event) => updateAndSave(menu.id, { starts_at: fromLimaInput(event.target.value) })} /> : <span className="text-sm text-muted-foreground">{unrestricted ? "Sin restricción" : "Desde: —"}</span>}</div>
          <div>{!unrestricted && draft.is_temporary ? <Input disabled={!canEditAccess} aria-label={`Hasta ${menu.nombre}`} type="datetime-local" value={toLimaInput(draft.ends_at)} onChange={(event) => updateAndSave(menu.id, { ends_at: fromLimaInput(event.target.value) })} /> : <span className="text-sm text-muted-foreground">{unrestricted ? "Sin restricción" : "Hasta: —"}</span>}</div>
          <div className="flex flex-col items-start gap-1"><span className="text-xs font-medium text-muted-foreground">{unrestricted || draft.is_active ? "Activo" : "Inactivo"}</span>{unrestricted ? <span className="font-medium text-emerald-700 dark:text-emerald-300">Sí</span> : <Switch disabled={!canEditAccess} checked={draft.is_active} onCheckedChange={(value) => updateAndSave(menu.id, { is_active: value })} />}</div>
        </div>;
      })}</div></section>)}</div>
      {!visibleRows.length && <p className="rounded-xl border border-dashed p-8 text-center text-sm text-muted-foreground">No hay opciones para los filtros actuales.</p>}
    </CardContent></Card>}
  </main>;
}
