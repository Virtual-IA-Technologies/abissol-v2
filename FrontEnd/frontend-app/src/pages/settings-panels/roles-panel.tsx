import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Pencil, Plus, Save, Trash2, UserPlus, UsersRound, X } from "lucide-react";
import { toast } from "sonner";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ActionButton } from "@/components/action-button";
import { ConfirmActionDialog } from "@/components/confirm-action-dialog";
import { ExcelDownloadButton } from "@/components/excel-download-button";
import { ListPagination } from "@/components/list-pagination";
import { RecordContextMenu } from "@/components/record-context-menu";
import { RowActionsMenu } from "@/components/row-actions-menu";
import { SearchableSelect } from "@/components/searchable-select";
import { SortableTableHead } from "@/components/sortable-table-head";
import { StandardListToolbar } from "@/components/standard-list-toolbar";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Sheet, SheetBody, SheetContent, SheetDescription, SheetFooter, SheetHeader, SheetSection, SheetSectionDescription, SheetSectionTitle, SheetTitle } from "@/components/ui/sheet";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { Table, TableBody, TableCell, TableFooter, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { useAuth } from "@/context/AuthContext";
import { usePlatformSettings } from "@/context/PlatformSettingsContext";
import { wolverineAPI } from "@/features/wolverine/api";
import type { Role, User } from "@/features/wolverine/types";
import { formatLimaDateTime, fromLimaInput, toLimaInput } from "@/lib/dates";
import { apiErrorMessage } from "@/lib/api-error";
import { compareTableValues, downloadExcelXlsx, includesSearch, nextSort, type SortDirection } from "@/lib/table-tools";
import { useListPagination } from "@/lib/use-list-pagination";
import { useIncomingSearch } from "@/lib/use-incoming-search";
import { useDoubleClickPreference } from "@/lib/use-double-click-preference";

const empty = { nombre: "", prioridad: 100, es_superusuario: false, is_active: true, is_default: false };
const emptyMembership = { userId: null as number | null, isPermanent: true, startsAt: "", endsAt: "" };
type RoleSort = "priority" | "name" | "users" | "status";
type RoleDoubleClick = "edit" | "users" | "none";
const ROLE_DOUBLE_CLICK: readonly RoleDoubleClick[] = ["edit", "users", "none"];

export default function RolesPanel() {
  const { can, user: currentUser } = useAuth();
  const { settings } = usePlatformSettings();
  const [roles, setRoles] = useState<Role[]>([]);
  const [users, setUsers] = useState<User[]>([]);
  const [viewingRoleId, setViewingRoleId] = useState<number | null>(null);
  const [editing, setEditing] = useState<number | null>(null);
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState(empty);
  const [busy, setBusy] = useState(false);
  const [search, setSearch] = useIncomingSearch();
  const [quickFilter, setQuickFilter] = useState("all");
  const [sortKey, setSortKey] = useState<RoleSort>("priority");
  const [sortDirection, setSortDirection] = useState<SortDirection>("asc");
  const [membership, setMembership] = useState(emptyMembership);
  const [membershipBusy, setMembershipBusy] = useState(false);
  const [membershipOpen, setMembershipOpen] = useState(false);
  const usersLoaded = useRef(false);
  const usersRequest = useRef<Promise<User[]> | null>(null);

  const canViewUsers = can("usuarios", "lector");
  const canEditRoles = can("roles", "editor");
  const [doubleClickAction, setDoubleClickAction] = useDoubleClickPreference<RoleDoubleClick>("roles", ROLE_DOUBLE_CLICK, canEditRoles ? "edit" : canViewUsers ? "users" : "none");
  const load = useCallback(() => wolverineAPI.roles().then(setRoles).catch((error) => toast.error(apiErrorMessage(error, "No se pudieron cargar los roles"))), []);
  useEffect(() => { void load(); }, [load]);

  const openUsers = useCallback(async (roleId: number) => {
    if (!canViewUsers) return;
    if (!usersLoaded.current) {
      usersRequest.current ??= wolverineAPI.users(true);
      try {
        setUsers(await usersRequest.current);
        usersLoaded.current = true;
      } catch (error) {
        usersRequest.current = null;
        toast.error(apiErrorMessage(error, "No se pudieron cargar los usuarios del rol"));
        return;
      }
    }
    setMembership(emptyMembership);
    setViewingRoleId(roleId);
  }, [canViewUsers]);

  const save = async () => {
    setBusy(true);
    try {
      if (editing) await wolverineAPI.updateRole(editing, form);
      else await wolverineAPI.createRole(form);
      setEditing(null); setShowForm(false); setForm(empty); await load(); toast.success("Rol guardado");
    } catch (error) { toast.error(apiErrorMessage(error, "No se pudo guardar el rol")); } finally { setBusy(false); }
  };
  const openEdit = (role: Role) => {
    if (!can("roles", "editor")) return;
    setEditing(role.id);
    setShowForm(true);
    setForm({ nombre: role.nombre, prioridad: role.prioridad, es_superusuario: role.es_superusuario, is_active: role.is_active, is_default: role.is_default });
  };

  const visibleRoles = useMemo(() => roles
    .filter((role) => includesSearch([role.nombre, role.prioridad, role.is_active ? "activo" : "inactivo"], search))
    .filter((role) => quickFilter === "all"
      || (quickFilter === "active" && role.is_active)
      || (quickFilter === "inactive" && !role.is_active)
      || (quickFilter === "superuser" && role.es_superusuario))
    .sort((left, right) => compareTableValues(
      sortKey === "priority" ? left.prioridad : sortKey === "name" ? left.nombre : sortKey === "users" ? left.user_ids.length : left.is_active ? 1 : 0,
      sortKey === "priority" ? right.prioridad : sortKey === "name" ? right.nombre : sortKey === "users" ? right.user_ids.length : right.is_active ? 1 : 0,
      sortDirection,
    )), [roles, search, quickFilter, sortKey, sortDirection]);
  const sortBy = (key: RoleSort) => {
    const [selectedKey, direction] = nextSort(sortKey, sortDirection, key);
    setSortKey(selectedKey); setSortDirection(direction);
  };
  const rolePagination = useListPagination(visibleRoles, [search, quickFilter, sortKey, sortDirection].join("|"));
  const assignmentTotal = visibleRoles.reduce((total, role) => total + role.user_ids.length, 0);
  const viewingRole = roles.find((role) => role.id === viewingRoleId);
  const assignedUsers = users.filter((user) => user.role_assignments.some((assignment) => assignment.rol_id === viewingRoleId));
  const editingMembership = membership.userId !== null && assignedUsers.some((user) => user.id === membership.userId);
  const isProgrammer = currentUser?.roles.some((role) => role.es_superusuario) ?? false;
  const canManageMembership = can("usuarios", "editor") && (!viewingRole?.es_superusuario || isProgrammer);
  const candidateUsers = users.filter((user) =>
    user.id === membership.userId || !user.role_assignments.some((assignment) => assignment.rol_id === viewingRoleId),
  );
  const acceptMembershipUser = (nextUser: User) => {
    setUsers((current) => {
      const nextUsers = current.map((user) => user.id === nextUser.id ? nextUser : user);
      usersLoaded.current = true;
      usersRequest.current = Promise.resolve(nextUsers);
      return nextUsers;
    });
    setRoles((current) => current.map((role) => {
      const assigned = nextUser.role_assignments.some((assignment) => assignment.rol_id === role.id);
      const userIds = assigned
        ? [...new Set([...role.user_ids, nextUser.id])]
        : role.user_ids.filter((userId) => userId !== nextUser.id);
      return { ...role, user_ids: userIds };
    }));
  };
  const editMembership = (user: User) => {
    const assignment = user.role_assignments.find((item) => item.rol_id === viewingRoleId);
    if (!assignment) return;
    setMembership({ userId: user.id, isPermanent: assignment.is_permanent, startsAt: toLimaInput(assignment.starts_at), endsAt: toLimaInput(assignment.ends_at) });
    setMembershipOpen(true);
    setMembershipOpen(true);
  };
  const saveMembership = async () => {
    if (!viewingRoleId || !membership.userId) return;
    if (!membership.isPermanent && (!membership.startsAt || !membership.endsAt || membership.endsAt <= membership.startsAt)) {
      toast.error("El rol temporal necesita inicio y fin, y el fin debe ser posterior");
      return;
    }
    setMembershipBusy(true);
    try {
      const nextUser = await wolverineAPI.saveRoleMembership(viewingRoleId, membership.userId, {
        is_permanent: membership.isPermanent,
        starts_at: membership.isPermanent ? null : fromLimaInput(membership.startsAt),
        ends_at: membership.isPermanent ? null : fromLimaInput(membership.endsAt),
      });
      acceptMembershipUser(nextUser);
      setMembership(emptyMembership);
      setMembershipOpen(false);
      toast.success("Asignación de rol guardada");
    } catch (error) {
      toast.error(apiErrorMessage(error, "No se pudo guardar la asignación"));
    } finally {
      setMembershipBusy(false);
    }
  };
  const removeMembership = async (user: User) => {
    if (!viewingRoleId) return;
    try {
      acceptMembershipUser(await wolverineAPI.deleteRoleMembership(viewingRoleId, user.id));
      if (membership.userId === user.id) setMembership(emptyMembership);
      toast.success("Usuario retirado del rol");
    } catch (error) {
      toast.error(apiErrorMessage(error, "No se pudo retirar al usuario del rol"));
      throw error;
    }
  };
  const contextActions = (role: Role) => [
    { label: "Ver usuarios", icon: UsersRound, disabled: !canViewUsers, onSelect: () => { void openUsers(role.id); } },
    { label: "Editar", icon: Pencil, disabled: !can("roles", "editor"), onSelect: () => openEdit(role) },
    { label: "Eliminar...", icon: Trash2, destructive: true, disabled: !can("roles", "gestor") || role.es_superusuario, onSelect: () => document.getElementById(`role-delete-${role.id}`)?.click() },
  ];
  const runDoubleClick = (role: Role) => {
    if (doubleClickAction === "edit" && canEditRoles) openEdit(role);
    if (doubleClickAction === "users" && canViewUsers) void openUsers(role.id);
  };
  const exportRoles = () => downloadExcelXlsx("roles", visibleRoles, [
    { header: "Prioridad", value: (role) => role.prioridad },
    { header: "Rol", value: (role) => role.nombre },
    { header: "Usuarios asignados", value: (role) => role.user_ids.length },
    { header: "Superior", value: (role) => role.es_superusuario ? "Si" : "No" },
    { header: "Estado", value: (role) => role.is_active ? "Activo" : "Inactivo" },
  ], { organizationName: settings.organization_name, criteria: { Busqueda: search || "Sin busqueda", Estado: quickFilter, Orden: `${sortKey}-${sortDirection}`, Registros: visibleRoles.length }, footer: ["", "TOTAL FILTRADO", assignmentTotal, "", ""] });

  return <main className="space-y-5 p-5 md:p-7">
    <div className="flex flex-wrap items-center justify-between gap-3"><div><h1 className="text-2xl font-semibold">Roles de ABISSOL</h1><p className="text-sm text-muted-foreground">Programador tiene nivel 0 y acceso gestor global.</p></div><div className="flex flex-wrap items-center gap-2">{can("roles", "editor") && <ActionButton tone="new" onClick={() => { setEditing(null); setForm(empty); setShowForm(true); }}><Plus className="size-4" />Nuevo rol</ActionButton>}<ExcelDownloadButton onDownload={exportRoles} disabled={visibleRoles.length === 0} /></div></div>
    <Sheet open={showForm} onOpenChange={setShowForm}><SheetContent className="w-full sm:max-w-xl"><SheetHeader><SheetTitle>{editing ? "Editar rol" : "Nuevo rol"}</SheetTitle><SheetDescription>Los roles se ordenan por prioridad y reciben permisos desde Accesos.</SheetDescription></SheetHeader>
      {can("roles", "editor") && <SheetBody><SheetSection><div><SheetSectionTitle>Identidad y jerarquía</SheetSectionTitle><SheetSectionDescription>La prioridad menor se evalúa primero al resolver los permisos.</SheetSectionDescription></div><div className="grid gap-5 sm:grid-cols-2">
        <div className="space-y-2"><Label>Nombre</Label><Input value={form.nombre} onChange={(e) => setForm({ ...form, nombre: e.target.value })} /></div>
        <div className="space-y-2"><Label>Prioridad</Label><Input type="number" value={form.prioridad} onChange={(e) => setForm({ ...form, prioridad: Number(e.target.value) })} /></div>
        <label className="flex items-center justify-between gap-4 rounded-xl border bg-muted/20 px-4 py-3.5 text-sm font-medium sm:col-span-2"><span><span className="block">Rol superior</span><span className="mt-1 block text-xs font-normal leading-5 text-muted-foreground">Otorga acceso total; úsalo únicamente para administradores de confianza.</span></span><Switch checked={form.es_superusuario} onCheckedChange={(value) => setForm({ ...form, es_superusuario: value })} /></label>
      </div></SheetSection></SheetBody>}<SheetFooter><Button variant="outline" onClick={() => setShowForm(false)}>Cancelar</Button><ActionButton tone={editing ? "edit" : "new"} onClick={save} disabled={busy || form.nombre.trim().length < 2}>{editing ? "Actualizar" : "Crear"}</ActionButton></SheetFooter>
    </SheetContent></Sheet>
    <Sheet open={viewingRoleId !== null && canViewUsers} onOpenChange={(open) => { if (!open) { setViewingRoleId(null); setMembershipOpen(false); setMembership(emptyMembership); } }}><SheetContent className="w-full sm:max-w-2xl"><SheetHeader><div className="flex items-start justify-between gap-4"><div><SheetTitle>Usuarios del rol {viewingRole?.nombre}</SheetTitle><SheetDescription>{assignedUsers.length} usuario{assignedUsers.length === 1 ? "" : "s"} asignado{assignedUsers.length === 1 ? "" : "s"}. La membresía modifica los accesos efectivos del usuario.</SheetDescription></div>{canManageMembership && <ActionButton tone="new" size="icon" title="Agregar usuario" aria-label={`Agregar usuario al rol ${viewingRole?.nombre ?? ""}`} onClick={() => { setMembership(emptyMembership); setMembershipOpen(true); }}><UserPlus className="size-4" /></ActionButton>}</div></SheetHeader><SheetBody>
      <div className="space-y-3">{assignedUsers.map((user) => { const assignment = user.role_assignments.find((item) => item.rol_id === viewingRoleId); return <div key={user.id} className="rounded-xl border bg-muted/15 p-4"><div className="flex items-start justify-between gap-3"><div><p className="font-semibold">{user.nombre} {user.apellido}</p><p className="text-sm text-muted-foreground">@{user.username} · {user.correo}</p></div><Badge variant={user.is_active ? "secondary" : "destructive"}>{user.is_active ? "Activo" : "Inactivo"}</Badge></div><div className="mt-3 flex items-center justify-between gap-3"><p className="text-xs text-muted-foreground">{assignment?.is_permanent ? "Asignación permanente" : `Temporal: ${formatLimaDateTime(assignment?.starts_at)} — ${formatLimaDateTime(assignment?.ends_at)}`}</p>{canManageMembership && <div className="flex shrink-0 gap-1.5"><ActionButton tone="edit" size="icon" title="Editar vigencia" aria-label={`Editar vigencia de ${user.nombre}`} onClick={() => editMembership(user)}><Pencil className="size-4" /></ActionButton><ConfirmActionDialog title="Retirar usuario del rol" description={`${user.nombre} ${user.apellido} dejará de recibir los accesos de ${viewingRole?.nombre}.`} confirmLabel="Retirar" destructive onConfirm={() => removeMembership(user)}><ActionButton tone="delete" size="icon" title="Retirar del rol" aria-label={`Retirar a ${user.nombre} del rol`}><Trash2 className="size-4" /></ActionButton></ConfirmActionDialog></div>}</div></div>; })}{!assignedUsers.length && <p className="rounded-xl border border-dashed p-8 text-center text-sm text-muted-foreground">Este rol no tiene usuarios asignados.</p>}</div>
    </SheetBody></SheetContent></Sheet>
    <Sheet open={membershipOpen && canManageMembership} onOpenChange={(open) => { setMembershipOpen(open); if (!open) setMembership(emptyMembership); }}><SheetContent className="w-full sm:max-w-xl"><SheetHeader><SheetTitle>{editingMembership ? "Editar vigencia" : "Agregar usuario"}</SheetTitle><SheetDescription>{editingMembership ? "Actualiza la vigencia de esta asignación." : `Agrega un usuario al rol ${viewingRole?.nombre ?? "seleccionado"}.`}</SheetDescription></SheetHeader><SheetBody><SheetSection><div><SheetSectionTitle>Asignación</SheetSectionTitle><SheetSectionDescription>El rol puede ser permanente o estar disponible solo dentro de un periodo.</SheetSectionDescription></div><div className="space-y-4">
      <div className="space-y-2"><Label htmlFor="role-member-user">Usuario</Label><SearchableSelect id="role-member-user" disabled={editingMembership} value={membership.userId ? String(membership.userId) : ""} onValueChange={(value) => setMembership({ ...membership, userId: value ? Number(value) : null })} options={candidateUsers.map((user) => ({ value: String(user.id), label: `${user.nombre} ${user.apellido} · @${user.username}${user.is_active ? "" : " · inactivo"}`, keywords: user.correo }))} placeholder="Seleccionar usuario..." searchPlaceholder="Escribe nombre, usuario o correo..." />{!candidateUsers.length && <p className="text-xs text-muted-foreground">No hay usuarios disponibles.</p>}</div>
      <div className="space-y-2"><Label htmlFor="role-member-validity">Vigencia</Label><SearchableSelect id="role-member-validity" value={membership.isPermanent ? "permanent" : "temporary"} onValueChange={(value) => setMembership({ ...membership, isPermanent: value === "permanent", startsAt: "", endsAt: "" })} options={[{ value: "permanent", label: "Permanente" }, { value: "temporary", label: "Temporal" }]} searchPlaceholder="Buscar vigencia..." /></div>
      {!membership.isPermanent && <div className="grid gap-4 sm:grid-cols-2"><div className="space-y-2"><Label htmlFor="role-member-start">Desde</Label><Input id="role-member-start" type="datetime-local" value={membership.startsAt} onChange={(event) => setMembership({ ...membership, startsAt: event.target.value })} /></div><div className="space-y-2"><Label htmlFor="role-member-end">Hasta</Label><Input id="role-member-end" type="datetime-local" value={membership.endsAt} onChange={(event) => setMembership({ ...membership, endsAt: event.target.value })} /></div></div>}
    </div></SheetSection></SheetBody><SheetFooter><Button type="button" variant="outline" onClick={() => setMembershipOpen(false)}><X className="size-4" />Cancelar</Button><ActionButton tone={editingMembership ? "edit" : "new"} disabled={membershipBusy || !membership.userId || (!membership.isPermanent && (!membership.startsAt || !membership.endsAt || membership.endsAt <= membership.startsAt))} onClick={() => { void saveMembership(); }}>{editingMembership ? <Save className="size-4" /> : <UserPlus className="size-4" />}{membershipBusy ? "Guardando…" : editingMembership ? "Guardar cambios" : "Agregar usuario"}</ActionButton></SheetFooter></SheetContent></Sheet>
    <Card className="gap-0 py-0"><CardContent className="space-y-3 p-4 md:p-5">
      <StandardListToolbar embedded resultLabel={`${visibleRoles.length} rol${visibleRoles.length === 1 ? "" : "es"} encontrado${visibleRoles.length === 1 ? "" : "s"}`} pagination={<ListPagination embedded compactWhenSinglePage {...rolePagination} totalItems={visibleRoles.length} onPageChange={rolePagination.setPage} onPageSizeChange={rolePagination.setPageSize} />} search={search} onSearchChange={setSearch} searchPlaceholder="Buscar rol, prioridad o estado..." filters={[
      { value: "all", label: "Todos", count: roles.length },
      { value: "active", label: "Activos", count: roles.filter((role) => role.is_active).length },
      { value: "inactive", label: "Inactivos", count: roles.filter((role) => !role.is_active).length },
      { value: "superuser", label: "Superiores", count: roles.filter((role) => role.es_superusuario).length },
    ]} activeFilter={quickFilter} onFilterChange={setQuickFilter} resultCount={visibleRoles.length} totalCount={roles.length} /><Table><TableHeader><TableRow><SortableTableHead label="Prioridad" active={sortKey === "priority"} direction={sortDirection} onSort={() => sortBy("priority")} /><SortableTableHead label="Rol" active={sortKey === "name"} direction={sortDirection} onSort={() => sortBy("name")} /><SortableTableHead label="Usuarios" active={sortKey === "users"} direction={sortDirection} onSort={() => sortBy("users")} /><SortableTableHead label="Estado" active={sortKey === "status"} direction={sortDirection} onSort={() => sortBy("status")} /><TableHead className="w-16 text-right">Opciones</TableHead></TableRow></TableHeader><TableBody>
      {rolePagination.pageItems.map((role) => { const doubleClickChoices = [...(canEditRoles ? [{ value: "edit" as const, label: "Editar" }] : []), ...(canViewUsers ? [{ value: "users" as const, label: "Ver usuarios" }] : []), { value: "none" as const, label: "Ninguna acción" }]; return <RecordContextMenu key={role.id} actions={contextActions(role)} doubleClick={{ value: doubleClickAction, onChange: setDoubleClickAction, choices: doubleClickChoices }}><TableRow title={`Doble clic: ${doubleClickAction === "edit" ? "editar" : doubleClickAction === "users" ? "ver usuarios" : "sin acción"}`} onDoubleClick={() => runDoubleClick(role)}><TableCell>{role.prioridad}</TableCell><TableCell className="font-medium">{role.nombre} {role.es_superusuario && <Badge className="ml-2">Superior</Badge>}</TableCell><TableCell><Badge variant="secondary" className="font-normal">{role.user_ids.length} usuario{role.user_ids.length === 1 ? "" : "s"}</Badge></TableCell><TableCell><Badge variant="outline" className={role.is_active ? "border-emerald-200 bg-emerald-50 text-emerald-700 dark:border-emerald-900 dark:bg-emerald-950/40 dark:text-emerald-300" : "text-muted-foreground"}>{role.is_active ? "Activo" : "Inactivo"}</Badge></TableCell><TableCell className="text-right" onDoubleClick={(event) => event.stopPropagation()}><div className="flex justify-end gap-1.5">
        <RowActionsMenu label={role.nombre} actions={contextActions(role).map((action) => ({ ...action, hidden: action.disabled }))} doubleClick={{ value: doubleClickAction, onChange: setDoubleClickAction, choices: doubleClickChoices }} />
        {can("roles", "gestor") && !role.es_superusuario && <ConfirmActionDialog title="Eliminar rol" description={`Se eliminará el rol ${role.nombre}. Esta acción no se puede deshacer.`} confirmLabel="Eliminar" destructive onConfirm={async () => { try { await wolverineAPI.deleteRole(role.id); await load(); toast.success("Rol eliminado"); } catch (error) { toast.error(apiErrorMessage(error, "No se pudo eliminar el rol")); throw error; } }}><button id={`role-delete-${role.id}`} type="button" className="hidden" aria-hidden="true" /></ConfirmActionDialog>}
      </div></TableCell></TableRow></RecordContextMenu>; })}
    </TableBody><TableFooter><TableRow><TableCell /><TableCell className="font-semibold">Total filtrado</TableCell><TableCell className="font-semibold">{assignmentTotal}</TableCell><TableCell colSpan={2} /></TableRow></TableFooter></Table></CardContent></Card>
  </main>;
}
