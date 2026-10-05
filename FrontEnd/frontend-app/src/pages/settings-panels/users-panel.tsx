import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Check, ChevronsUpDown, Circle, Eye, KeyRound, Pencil, Plus, Power, PowerOff, Save, ShieldCheck, Trash2, X } from "lucide-react";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { ActionButton } from "@/components/action-button";
import { ConfirmActionDialog } from "@/components/confirm-action-dialog";
import { ExcelDownloadButton } from "@/components/excel-download-button";
import { ListPagination } from "@/components/list-pagination";
import { RecordContextMenu } from "@/components/record-context-menu";
import { RowActionsMenu } from "@/components/row-actions-menu";
import { SortableTableHead } from "@/components/sortable-table-head";
import { StandardListToolbar } from "@/components/standard-list-toolbar";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import { Command, CommandEmpty, CommandGroup, CommandInput, CommandItem, CommandList } from "@/components/ui/command";
import { Sheet, SheetBody, SheetContent, SheetDescription, SheetFooter, SheetHeader, SheetSection, SheetSectionDescription, SheetSectionTitle, SheetTitle } from "@/components/ui/sheet";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { useAuth } from "@/context/AuthContext";
import { usePlatformSettings } from "@/context/PlatformSettingsContext";
import { wolverineAPI } from "@/features/wolverine/api";
import type { CredentialNotificationResult, Role, User, UserRoleAssignmentWrite } from "@/features/wolverine/types";
import { apiErrorMessage } from "@/lib/api-error";
import { fromLimaInput, toLimaInput } from "@/lib/dates";
import { compareTableValues, downloadExcelXlsx, includesSearch, nextSort, type SortDirection } from "@/lib/table-tools";
import { useListPagination } from "@/lib/use-list-pagination";
import { useIncomingSearch } from "@/lib/use-incoming-search";
import { useDoubleClickPreference } from "@/lib/use-double-click-preference";

function temporaryPassword() {
  const bytes = crypto.getRandomValues(new Uint8Array(12));
  const chars = "ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz23456789";
  return `Wv!${Array.from(bytes, (value) => chars[value % chars.length]).join("")}`;
}

const blank = () => ({
  nombre: "", apellido: "", username: "", correo: "", telefono: "",
  role_assignments: [] as UserRoleAssignmentWrite[], contrasena: temporaryPassword(),
  notificar_correo: false, notificar_whatsapp: false,
});

function deliverySummary(results: CredentialNotificationResult[]) {
  if (!results.length) return "Sin notificación externa solicitada";
  return results.map((result) => `${result.canal === "correo" ? "Correo" : "WhatsApp"}: ${result.detalle}`).join(" · ");
}

type UserSort = "name" | "username" | "contact" | "roles" | "status";
type UserDoubleClick = "edit" | "access" | "none";
const USER_DOUBLE_CLICK: readonly UserDoubleClick[] = ["edit", "access", "none"];

const userSortValue = (user: User, key: UserSort) => ({
  name: `${user.nombre} ${user.apellido}`,
  username: user.username,
  contact: user.correo,
  roles: user.role_assignments.map((assignment) => assignment.rol.nombre).join(" "),
  status: user.is_active ? 1 : 0,
})[key];

export default function UsersPanel() {
  const auth = useAuth();
  const navigate = useNavigate();
  const { settings } = usePlatformSettings();
  const [users, setUsers] = useState<User[]>([]);
  const [roles, setRoles] = useState<Role[]>([]);
  const [editing, setEditing] = useState<number | null>(null);
  const [showForm, setShowForm] = useState(false);
  const [saving, setSaving] = useState(false);
  const [form, setForm] = useState(blank);
  const [resetUser, setResetUser] = useState<User | null>(null);
  const [resetChannels, setResetChannels] = useState({ notificar_correo: false, notificar_whatsapp: false });
  const [search, setSearch] = useIncomingSearch();
  const [quickFilter, setQuickFilter] = useState("all");
  const [sortKey, setSortKey] = useState<UserSort>("name");
  const [sortDirection, setSortDirection] = useState<SortDirection>("asc");
  const rolesLoaded = useRef(false);
  const rolesRequest = useRef<Promise<Role[]> | null>(null);

  const load = useCallback(async () => {
    try {
      setUsers(await wolverineAPI.users(true));
    } catch (error) {
      toast.error(apiErrorMessage(error, "No se pudieron cargar los usuarios"));
    }
  }, []);

  useEffect(() => {
    const refresh = () => { if (document.visibilityState === 'visible') void load(); };
    refresh();
    window.addEventListener('focus', refresh);
    return () => window.removeEventListener('focus', refresh);
  }, [load]);

  const ensureRoles = useCallback(async () => {
    if (rolesLoaded.current) return true;
    rolesRequest.current ??= wolverineAPI.roles();
    try {
      setRoles(await rolesRequest.current);
      rolesLoaded.current = true;
      return true;
    } catch (error) {
      rolesRequest.current = null;
      toast.error(apiErrorMessage(error, "No se pudieron cargar los roles del formulario"));
      return false;
    }
  }, []);

  const closeForm = () => {
    setEditing(null);
    setShowForm(false);
    setForm(blank());
  };

  const openCreate = async () => {
    if (!await ensureRoles()) return;
    setEditing(null);
    setForm(blank());
    setShowForm(true);
  };

  const openEdit = async (user: User) => {
    if (!canEdit) return;
    if (!await ensureRoles()) return;
    setEditing(user.id);
    setShowForm(true);
    setForm({ nombre: user.nombre, apellido: user.apellido, username: user.username, correo: user.correo, telefono: user.telefono ?? "", role_assignments: user.role_assignments.map((assignment) => ({ rol_id: assignment.rol_id, is_permanent: assignment.is_permanent, starts_at: toLimaInput(assignment.starts_at), ends_at: toLimaInput(assignment.ends_at) })), contrasena: "", notificar_correo: false, notificar_whatsapp: false });
  };

  const save = async () => {
    setSaving(true);
    try {
      const base = {
        nombre: form.nombre.trim(), apellido: form.apellido.trim(), username: form.username.trim(),
        correo: form.correo.trim(), telefono: form.telefono.trim() || null,
        role_assignments: form.role_assignments.map((assignment) => ({
          ...assignment,
          starts_at: fromLimaInput(assignment.starts_at),
          ends_at: fromLimaInput(assignment.ends_at),
        })),
      };
      if (editing) {
        await wolverineAPI.updateUser(editing, base);
        toast.success("Usuario actualizado");
      } else {
        const result = await wolverineAPI.createUser({
          ...base, contrasena: form.contrasena,
          notificar_correo: form.notificar_correo,
          notificar_whatsapp: form.notificar_whatsapp,
        });
        const failed = result.notificaciones.some((item) => !item.enviado);
        const message = `Usuario creado. Clave temporal: ${form.contrasena}. ${deliverySummary(result.notificaciones)}`;
        if (failed) toast.warning(message, { duration: 20_000 });
        else toast.success(message, { duration: 15_000 });
      }
      closeForm();
      await load();
    } catch (error) {
      toast.error(apiErrorMessage(error, "No se pudo guardar el usuario"));
    } finally {
      setSaving(false);
    }
  };

  const runAction = async (action: () => Promise<unknown>, success: string) => {
    try {
      await action();
      toast.success(success);
      await load();
    } catch (error) {
      toast.error(apiErrorMessage(error, "No se pudo completar la acción"));
    }
  };

  const resetPassword = async () => {
    if (!resetUser) return;
    try {
      const result = await wolverineAPI.resetUserPassword(resetUser.id, resetChannels);
      const failed = result.notificaciones.some((item) => !item.enviado);
      const message = `Clave temporal: ${result.clave_temporal}. ${deliverySummary(result.notificaciones)}`;
      if (failed) toast.warning(message, { duration: 20_000 });
      else toast.success(message, { duration: 15_000 });
      setResetUser(null);
      setResetChannels({ notificar_correo: false, notificar_whatsapp: false });
    } catch (error) {
      toast.error(apiErrorMessage(error, "No se pudo restablecer la clave"));
      throw error;
    }
  };

  const isProgrammer = auth.user?.roles.some((role) => role.es_superusuario) ?? false;
  const canEdit = auth.can("usuarios", "editor");
  const canManage = auth.can("usuarios", "gestor");
  const canViewAccess = auth.can("accesos", "lector");
  const [doubleClickAction, setDoubleClickAction] = useDoubleClickPreference<UserDoubleClick>("usuarios", USER_DOUBLE_CLICK, canEdit ? "edit" : canViewAccess ? "access" : "none");
  const openAccess = (user: User) => navigate(`/plataforma/administracion/accesos?tipo=usuario&id=${user.id}&origen=usuarios`);
  const runDoubleClick = (user: User) => {
    if (doubleClickAction === "edit" && canEdit) void openEdit(user);
    if (doubleClickAction === "access" && canViewAccess) openAccess(user);
  };
  const startImpersonation = async (user: User) => {
    try {
      await auth.startImpersonation(user.id);
      toast.success(`Ahora estás viendo ABISSOL V2 como ${user.nombre}`);
      navigate("/home");
    } catch (error) {
      toast.error(apiErrorMessage(error, "No se pudo iniciar la impersonación"));
    }
  };
  const contextActions = (user: User) => [
    { label: "Editar", icon: Pencil, disabled: !canEdit, onSelect: () => { void openEdit(user); } },
    { label: "Ver accesos", icon: ShieldCheck, disabled: !canViewAccess, onSelect: () => openAccess(user) },
    { label: "Restablecer clave...", icon: KeyRound, disabled: !canEdit || !user.is_active, onSelect: () => { setResetChannels({ notificar_correo: false, notificar_whatsapp: false }); setResetUser(user); } },
    { label: user.is_active ? "Desactivar..." : "Activar...", icon: user.is_active ? PowerOff : Power, destructive: user.is_active, disabled: !canManage || user.id === auth.user?.id || (user.roles.some((role) => role.es_superusuario) && !isProgrammer), onSelect: () => document.getElementById(`user-state-${user.id}`)?.click() },
    { label: "Eliminar...", icon: Trash2, destructive: true, disabled: !canManage || user.id === auth.user?.id || (user.roles.some((role) => role.es_superusuario) && !isProgrammer), onSelect: () => document.getElementById(`user-delete-${user.id}`)?.click() },
    ...(isProgrammer ? [{ label: "Entrar como este usuario", icon: Eye, disabled: !user.is_active || user.id === auth.user?.id || user.roles.some((role) => role.es_superusuario), onSelect: () => { void startImpersonation(user); } }] : []),
  ];
  const visibleUsers = useMemo(() => users
    .filter((user) => includesSearch([
      user.nombre, user.apellido, user.username, user.correo, user.telefono,
      ...user.role_assignments.map((assignment) => assignment.rol.nombre),
    ], search))
    .filter((user) => quickFilter === "all"
      || (quickFilter === "active" && user.is_active)
      || (quickFilter === "inactive" && !user.is_active)
      || (quickFilter === "temporary" && user.role_assignments.some((assignment) => !assignment.is_permanent))
      || (quickFilter === "without-role" && user.role_assignments.length === 0))
    .sort((left, right) => compareTableValues(userSortValue(left, sortKey), userSortValue(right, sortKey), sortDirection)),
  [users, search, quickFilter, sortKey, sortDirection]);
  const sortBy = (key: UserSort) => {
    const [selectedKey, direction] = nextSort(sortKey, sortDirection, key);
    setSortKey(selectedKey);
    setSortDirection(direction);
  };
  const userPagination = useListPagination(visibleUsers, [search, quickFilter, sortKey, sortDirection].join("|"));
  const exportUsers = () => downloadExcelXlsx("usuarios", visibleUsers, [
    { header: "Nombre", value: (user) => `${user.nombre} ${user.apellido}` },
    { header: "Usuario", value: (user) => user.username },
    { header: "Correo", value: (user) => user.correo },
    { header: "Telefono", value: (user) => user.telefono },
    { header: "Roles", value: (user) => user.role_assignments.map((assignment) => `${assignment.rol.nombre}${assignment.is_permanent ? "" : " (temporal)"}`).join(", ") },
    { header: "Estado", value: (user) => user.is_active ? "Activo" : "Inactivo" },
  ], { organizationName: settings.organization_name, criteria: { Busqueda: search || "Sin busqueda", Estado: quickFilter, Orden: `${sortKey}-${sortDirection}`, Registros: visibleUsers.length } });

  return <main className="space-y-5 p-5 md:p-7">
    <div className="flex flex-wrap items-center justify-between gap-3">
      <div><h1 className="text-2xl font-semibold">Usuarios</h1><p className="text-sm text-muted-foreground">Cuentas, roles e identificadores de acceso.</p></div>
      <div className="flex flex-wrap items-center gap-2">{canEdit && <ActionButton tone="new" onClick={() => { void openCreate(); }}><Plus className="size-4" />Nuevo usuario</ActionButton>}<ExcelDownloadButton onDownload={exportUsers} disabled={visibleUsers.length === 0} /></div>
    </div>

    <Sheet open={showForm && canEdit} onOpenChange={(open) => { if (!open) closeForm(); }}><SheetContent className="w-full sm:max-w-2xl">
      <SheetHeader><SheetTitle>{editing ? "Editar usuario" : "Nuevo usuario"}</SheetTitle><SheetDescription>Podrá iniciar sesión con su correo, nombre de usuario o teléfono.</SheetDescription></SheetHeader>
      <SheetBody className="space-y-7">
        <SheetSection><div><SheetSectionTitle>Datos de acceso</SheetSectionTitle><SheetSectionDescription>Identificación personal y credenciales utilizadas para iniciar sesión.</SheetSectionDescription></div><div className="grid gap-x-5 gap-y-5 sm:grid-cols-2">
          <div className="space-y-2"><Label htmlFor="user-name">Nombre</Label><Input id="user-name" value={form.nombre} onChange={(event) => setForm({ ...form, nombre: event.target.value })} /></div>
          <div className="space-y-2"><Label htmlFor="user-lastname">Apellido</Label><Input id="user-lastname" value={form.apellido} onChange={(event) => setForm({ ...form, apellido: event.target.value })} /></div>
          <div className="space-y-2"><Label htmlFor="username">Usuario</Label><Input id="username" autoComplete="off" value={form.username} onChange={(event) => setForm({ ...form, username: event.target.value.toLowerCase().replace(/[^a-z0-9._-]/g, "") })} placeholder="nombre.apellido" /></div>
          <div className="space-y-2"><Label htmlFor="user-email">Correo</Label><Input id="user-email" type="email" value={form.correo} onChange={(event) => setForm({ ...form, correo: event.target.value })} /></div>
          <div className="space-y-2"><Label htmlFor="user-phone">Teléfono</Label><Input id="user-phone" type="tel" inputMode="numeric" maxLength={9} value={form.telefono} onChange={(event) => setForm({ ...form, telefono: event.target.value.replace(/\D/g, "").slice(0, 9) })} placeholder="999999999" /><p className="text-xs text-muted-foreground">Solo el número local, sin +51.</p></div>
          {!editing && <div className="space-y-2"><Label htmlFor="temporary-password">Clave temporal</Label><Input id="temporary-password" value={form.contrasena} onChange={(event) => setForm({ ...form, contrasena: event.target.value })} /></div>}
        </div></SheetSection>
        {!editing && <SheetSection><div><SheetSectionTitle>Notificar credenciales</SheetSectionTitle><SheetSectionDescription>El envío es opcional y usa las configuraciones globales activas. ABISSOL mostrará el resultado de cada canal.</SheetSectionDescription></div><div className="space-y-4">
          <div className="flex items-center justify-between gap-4 rounded-xl border p-4"><div><Label htmlFor="notify-user-email">Correo</Label><p className="text-xs text-muted-foreground">Enviar usuario y clave temporal a {form.correo.trim() || "su correo"}.</p></div><Switch id="notify-user-email" checked={form.notificar_correo} onCheckedChange={(checked) => setForm({ ...form, notificar_correo: checked })} /></div>
          <div className="flex items-center justify-between gap-4 rounded-xl border p-4"><div><Label htmlFor="notify-user-whatsapp">WhatsApp</Label><p className="text-xs text-muted-foreground">Requiere un teléfono local y WhatsApp activo.</p></div><Switch id="notify-user-whatsapp" checked={form.notificar_whatsapp} onCheckedChange={(checked) => setForm({ ...form, notificar_whatsapp: checked })} /></div>
        </div></SheetSection>}
        <SheetSection><div><SheetSectionTitle>Roles y vigencia</SheetSectionTitle><SheetSectionDescription>Asigna uno o más roles y define si el acceso es permanente o temporal.</SheetSectionDescription></div><div className="space-y-2"><Label>Roles</Label><Popover><PopoverTrigger asChild><Button type="button" variant="outline" role="combobox" className="h-10 w-full justify-between rounded-lg font-normal"><span className="truncate">{form.role_assignments.length ? `${form.role_assignments.length} rol${form.role_assignments.length === 1 ? "" : "es"} seleccionado${form.role_assignments.length === 1 ? "" : "s"}` : "Seleccionar roles"}</span><ChevronsUpDown className="size-4 opacity-50" /></Button></PopoverTrigger><PopoverContent className="w-[var(--radix-popover-trigger-width)] p-0" align="start"><Command><CommandInput placeholder="Buscar rol…" /><CommandList><CommandEmpty>No se encontraron roles.</CommandEmpty><CommandGroup>{roles.filter((role) => role.is_active).map((role) => { const selected = form.role_assignments.some((item) => item.rol_id === role.id); const disabled = role.es_superusuario && !isProgrammer; return <CommandItem key={role.id} disabled={disabled} value={role.nombre} onSelect={() => setForm({ ...form, role_assignments: selected ? form.role_assignments.filter((item) => item.rol_id !== role.id) : [...form.role_assignments, { rol_id: role.id, is_permanent: true, starts_at: null, ends_at: null }] })}><Check className={selected ? "opacity-100" : "opacity-0"} />{role.nombre}</CommandItem>; })}</CommandGroup></CommandList></Command></PopoverContent></Popover></div>
        {form.role_assignments.length > 0 && <div className="space-y-3"><Label>Vigencia de los roles</Label>{form.role_assignments.map((assignment) => { const role = roles.find((item) => item.id === assignment.rol_id); return <div key={assignment.rol_id} className="space-y-4 rounded-xl border bg-background p-4"><div className="flex items-center justify-between gap-3"><span className="font-semibold">{role?.nombre ?? `Rol ${assignment.rol_id}`}</span><Button type="button" size="sm" variant="ghost" onClick={() => setForm({ ...form, role_assignments: form.role_assignments.filter((item) => item.rol_id !== assignment.rol_id) })}>Quitar</Button></div><Select value={assignment.is_permanent ? "permanent" : "temporary"} onValueChange={(value) => setForm({ ...form, role_assignments: form.role_assignments.map((item) => item.rol_id === assignment.rol_id ? { ...item, is_permanent: value === "permanent", starts_at: null, ends_at: null } : item) })}><SelectTrigger className="h-10 w-full rounded-lg"><SelectValue /></SelectTrigger><SelectContent><SelectItem value="permanent">Permanente</SelectItem><SelectItem value="temporary">Temporal</SelectItem></SelectContent></Select>{!assignment.is_permanent && <div className="grid gap-4 sm:grid-cols-2"><div className="space-y-2"><Label>Desde</Label><Input type="datetime-local" value={assignment.starts_at ?? ""} onChange={(event) => setForm({ ...form, role_assignments: form.role_assignments.map((item) => item.rol_id === assignment.rol_id ? { ...item, starts_at: event.target.value || null } : item) })} /></div><div className="space-y-2"><Label>Hasta</Label><Input type="datetime-local" value={assignment.ends_at ?? ""} onChange={(event) => setForm({ ...form, role_assignments: form.role_assignments.map((item) => item.rol_id === assignment.rol_id ? { ...item, ends_at: event.target.value || null } : item) })} /></div></div>}</div>; })}</div>}
        </SheetSection>
      </SheetBody><SheetFooter><Button variant="outline" onClick={closeForm}><X className="size-4" />Cancelar</Button><ActionButton tone={editing ? "edit" : "new"} onClick={save} disabled={saving || !form.nombre.trim() || (!editing && !form.apellido.trim()) || (form.username.trim().length < 3 && form.username !== users.find(user => user.id === editing)?.username) || (!editing && !form.correo.trim()) || (!editing && form.notificar_whatsapp && !form.telefono.trim()) || form.role_assignments.some((item) => !item.is_permanent && (!item.starts_at || !item.ends_at || item.ends_at <= item.starts_at))}><Save className="size-4" />{saving ? "Guardando…" : "Guardar"}</ActionButton></SheetFooter>
    </SheetContent></Sheet>

    <Sheet open={Boolean(resetUser) && canEdit} onOpenChange={(open) => { if (!open) setResetUser(null); }}><SheetContent className="w-full sm:max-w-xl">
      <SheetHeader><SheetTitle>Restablecer contraseña</SheetTitle><SheetDescription>Se cerrarán las sesiones de {resetUser?.nombre} y se generará una nueva clave temporal.</SheetDescription></SheetHeader>
      <SheetBody className="space-y-7"><SheetSection><div><SheetSectionTitle>Canales de entrega</SheetSectionTitle><SheetSectionDescription>Selecciona cómo comunicar la clave. Si un envío falla, la clave se mostrará para entrega manual.</SheetSectionDescription></div><div className="space-y-4">
        <div className="flex items-center justify-between gap-4 rounded-xl border p-4"><div><Label htmlFor="reset-notify-email">Correo</Label><p className="text-xs text-muted-foreground">{resetUser?.correo}</p></div><Switch id="reset-notify-email" checked={resetChannels.notificar_correo} onCheckedChange={(checked) => setResetChannels((current) => ({ ...current, notificar_correo: checked }))} /></div>
        <div className="flex items-center justify-between gap-4 rounded-xl border p-4"><div><Label htmlFor="reset-notify-whatsapp">WhatsApp</Label><p className="text-xs text-muted-foreground">{resetUser?.telefono || "El usuario no tiene teléfono"}</p></div><Switch id="reset-notify-whatsapp" disabled={!resetUser?.telefono} checked={resetChannels.notificar_whatsapp} onCheckedChange={(checked) => setResetChannels((current) => ({ ...current, notificar_whatsapp: checked }))} /></div>
      </div></SheetSection></SheetBody>
      <SheetFooter><Button variant="outline" onClick={() => setResetUser(null)}>Cancelar</Button><ConfirmActionDialog title="Confirmar restablecimiento" description={`Se revocarán las sesiones de ${resetUser?.nombre} y la clave anterior dejará de funcionar.`} confirmLabel="Restablecer" onConfirm={resetPassword}><ActionButton tone="edit"><KeyRound className="size-4" />Restablecer clave</ActionButton></ConfirmActionDialog></SheetFooter>
    </SheetContent></Sheet>

    <Card className="gap-0 py-0"><CardContent className="space-y-3 p-4 md:p-5">
      <StandardListToolbar embedded resultLabel={`${visibleUsers.length} usuario${visibleUsers.length === 1 ? "" : "s"} encontrado${visibleUsers.length === 1 ? "" : "s"}`} pagination={<ListPagination embedded compactWhenSinglePage {...userPagination} totalItems={visibleUsers.length} onPageChange={userPagination.setPage} onPageSizeChange={userPagination.setPageSize} />} search={search} onSearchChange={setSearch} searchPlaceholder="Buscar persona, usuario, correo, teléfono o rol..." filters={[
      { value: "all", label: "Todos", count: users.length },
      { value: "active", label: "Activos", count: users.filter((user) => user.is_active).length },
      { value: "inactive", label: "Inactivos", count: users.filter((user) => !user.is_active).length },
      { value: "temporary", label: "Rol temporal", count: users.filter((user) => user.role_assignments.some((assignment) => !assignment.is_permanent)).length },
      { value: "without-role", label: "Sin rol", count: users.filter((user) => user.role_assignments.length === 0).length },
    ]} activeFilter={quickFilter} onFilterChange={setQuickFilter} resultCount={visibleUsers.length} totalCount={users.length} /><Table><TableHeader><TableRow><SortableTableHead label="Persona" active={sortKey === "name"} direction={sortDirection} onSort={() => sortBy("name")} /><SortableTableHead label="Usuario" active={sortKey === "username"} direction={sortDirection} onSort={() => sortBy("username")} /><SortableTableHead label="Contacto" active={sortKey === "contact"} direction={sortDirection} onSort={() => sortBy("contact")} /><SortableTableHead label="Roles" active={sortKey === "roles"} direction={sortDirection} onSort={() => sortBy("roles")} /><SortableTableHead label="Estado" active={sortKey === "status"} direction={sortDirection} onSort={() => sortBy("status")} /><TableHead className="w-16 text-right">Opciones</TableHead></TableRow></TableHeader><TableBody>{userPagination.pageItems.map((user) => { const managementProtected = user.id === auth.user?.id || (user.roles.some((role) => role.es_superusuario) && !isProgrammer); const impersonationProtected = user.id === auth.user?.id || user.roles.some((role) => role.es_superusuario); const doubleClickChoices = [...(canEdit ? [{ value: "edit" as const, label: "Editar" }] : []), ...(canViewAccess ? [{ value: "access" as const, label: "Ver accesos" }] : []), { value: "none" as const, label: "Ninguna acción" }]; return <RecordContextMenu key={user.id} actions={contextActions(user)} doubleClick={{ value: doubleClickAction, onChange: setDoubleClickAction, choices: doubleClickChoices }}><TableRow className={!user.is_active ? "opacity-60" : undefined} title={`Doble clic: ${doubleClickAction === "edit" ? "editar" : doubleClickAction === "access" ? "ver accesos" : "sin acción"}`} onDoubleClick={() => runDoubleClick(user)}><TableCell className="font-medium">{user.nombre} {user.apellido}</TableCell><TableCell className="font-mono text-xs">{user.username}</TableCell><TableCell><div>{user.correo}</div><div className="text-xs text-muted-foreground">{user.telefono || "Sin teléfono"}</div></TableCell><TableCell><div className="flex flex-wrap gap-1">{user.role_assignments.length ? user.role_assignments.map((assignment) => <Badge key={assignment.rol_id} variant="secondary" className="font-normal">{assignment.rol.nombre}{assignment.is_permanent ? "" : " · temporal"}</Badge>) : <span className="text-muted-foreground">Sin rol</span>}</div></TableCell><TableCell><Badge variant="outline" className={user.is_active ? "border-emerald-200 bg-emerald-50 text-emerald-700 dark:border-emerald-900 dark:bg-emerald-950/40 dark:text-emerald-300" : "text-muted-foreground"}><Circle className={user.is_active ? "fill-emerald-500 text-emerald-500" : "fill-muted-foreground text-muted-foreground"} />{user.is_active ? "Activo" : "Inactivo"}</Badge></TableCell><TableCell onDoubleClick={(event) => event.stopPropagation()}><div className="flex justify-end gap-1.5">
      <RowActionsMenu label={user.nombre} actions={contextActions(user).map((action) => ({ ...action, hidden: action.disabled }))} doubleClick={{ value: doubleClickAction, onChange: setDoubleClickAction, choices: doubleClickChoices }} />
      {isProgrammer && user.is_active && !impersonationProtected && <Button type="button" size="icon" variant="ghost" title={`Entrar como ${user.nombre}`} aria-label={`Entrar como ${user.nombre}`} onClick={() => { void startImpersonation(user); }}><Eye className="size-4" /></Button>}
      {canManage && !managementProtected && (user.is_active ? <ConfirmActionDialog title="Desactivar usuario" description={`${user.nombre} perderá acceso y sus sesiones serán revocadas.`} confirmLabel="Desactivar" destructive onConfirm={() => runAction(() => wolverineAPI.deactivateUser(user.id), "Usuario desactivado")}><button id={`user-state-${user.id}`} type="button" className="hidden" aria-hidden="true" /></ConfirmActionDialog> : <ConfirmActionDialog title="Activar usuario" description={`${user.nombre} podrá volver a iniciar sesión.`} confirmLabel="Activar" onConfirm={() => runAction(() => wolverineAPI.activateUser(user.id), "Usuario activado")}><button id={`user-state-${user.id}`} type="button" className="hidden" aria-hidden="true" /></ConfirmActionDialog>)}
      {canManage && !managementProtected && <ConfirmActionDialog title="Eliminar usuario" description={`${user.nombre} perderá definitivamente el acceso. Sus identificadores se anonimizarán y el movimiento quedará en Auditoría.`} confirmLabel="Eliminar" destructive onConfirm={() => runAction(() => wolverineAPI.deleteUser(user.id), "Usuario eliminado")}><button id={`user-delete-${user.id}`} type="button" className="hidden" aria-hidden="true" /></ConfirmActionDialog>}
    </div></TableCell></TableRow></RecordContextMenu>; })}</TableBody></Table></CardContent></Card>
  </main>;
}
