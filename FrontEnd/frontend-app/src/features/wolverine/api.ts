import api, { sessionClient } from "@/lib/api";
import type { AccessGrant, AccessLevel, GlobalSearchResponse, MenuNode, NavigationLayout, Role, ThemeAppearanceCustomization, ThemeName, User, UserCreateResult, UserPasswordResetResult, UserRoleAssignmentWrite, WolverineSession } from "./types";

export const wolverineAPI = {
  login: async (identificador: string, contrasena: string, rememberMe: boolean) =>
    (await sessionClient.post<WolverineSession>("/login", { identificador, contrasena, rememberMe })).data,
  requestPasswordReset: async (correo: string) =>
    (await sessionClient.post<{ message: string }>("/password-reset/request", { correo })).data,
  completePasswordReset: async (payload: { token: string; nueva_clave: string; confirmar_clave: string }) =>
    (await sessionClient.post<{ message: string }>("/password-reset/complete", payload)).data,
  logout: async () => { await api.post("/logout-session"); },
  me: async () => (await api.get<WolverineSession>("/me")).data,
  globalSearch: async (query: string, signal?: AbortSignal) => (await api.get<GlobalSearchResponse>("/busqueda-global", { params: { q: query }, signal })).data,
  updateMyAccount: async (payload: { nombre: string; apellido: string; username: string; correo: string; telefono: string | null }) =>
    (await api.put<User>("/mi-cuenta", payload)).data,
  updateMyPreferences: async (payload: { tema: ThemeName; escala: number; navigation_layout: NavigationLayout; menu_palette: "theme" | "custom"; background_palette: "theme" | "custom"; menu_color: string; menu_tone: number; background_color: string; background_tone: number; appearance_overrides: Partial<Record<ThemeName, ThemeAppearanceCustomization>> }) =>
    (await api.put<typeof payload>("/mi-cuenta/preferencias", payload)).data,
  updateMyTheme: async (tema: ThemeName) =>
    (await api.put<{ tema: ThemeName }>("/mi-cuenta/tema", { tema })).data,
  updateMyPassword: async (payload: { clave_actual: string; nueva_clave: string; confirmar_clave: string }) =>
    (await api.put<{ message: string }>("/mi-cuenta/clave", payload)).data,
  uploadMyAvatar: async (avatar: File) => {
    const form = new FormData(); form.append("avatar", avatar);
    return (await api.post<User>("/mi-cuenta/avatar", form)).data;
  },
  deleteMyAvatar: async () => (await api.delete<User>("/mi-cuenta/avatar")).data,
  startImpersonation: async (userId: number) =>
    (await api.post<WolverineSession>(`/impersonation/start/${userId}`)).data,
  leaveImpersonation: async () =>
    (await api.post<WolverineSession>("/impersonation/leave")).data,
  changePassword: async (payload: { nueva_clave: string; confirmar_clave: string }) =>
    (await api.post("/cambiar-clave-obligatoria", payload)).data,
  users: async (includeInactive = false) => (await api.get<User[]>("/usuarios", { params: { include_inactive: includeInactive } })).data,
  createUser: async (payload: { nombre: string; apellido: string; username: string; correo: string; telefono: string | null; role_assignments: UserRoleAssignmentWrite[]; contrasena: string; notificar_correo: boolean; notificar_whatsapp: boolean }) =>
    (await api.post<UserCreateResult>("/usuarios", payload)).data,
  updateUser: async (id: number, payload: { nombre: string; apellido: string; username: string; correo: string; telefono: string | null; role_assignments: UserRoleAssignmentWrite[] }) =>
    (await api.put<User>(`/usuarios/${id}`, payload)).data,
  deactivateUser: async (id: number) => (await api.post<User>(`/usuarios/${id}/desactivar`, {})).data,
  activateUser: async (id: number) => (await api.post<User>(`/usuarios/${id}/activar`)).data,
  deleteUser: async (id: number) => { await api.delete(`/usuarios/${id}`); },
  resetUserPassword: async (id: number, payload: { notificar_correo: boolean; notificar_whatsapp: boolean }) =>
    (await api.post<UserPasswordResetResult>(`/usuarios/${id}/restablecer-clave`, payload)).data,
  roles: async () => (await api.get<Role[]>("/roles")).data,
  createRole: async (payload: Omit<Role, "id" | "user_ids">) =>
    (await api.post<Role>("/roles", payload)).data,
  updateRole: async (id: number, payload: Partial<Role>) =>
    (await api.put<Role>(`/roles/${id}`, payload)).data,
  deleteRole: async (id: number) => { await api.delete(`/roles/${id}`); },
  saveRoleMembership: async (roleId: number, userId: number, payload: Omit<UserRoleAssignmentWrite, "rol_id">) =>
    (await api.put<User>(`/roles/${roleId}/usuarios/${userId}`, payload)).data,
  deleteRoleMembership: async (roleId: number, userId: number) =>
    (await api.delete<User>(`/roles/${roleId}/usuarios/${userId}`)).data,
  menus: async () => (await api.get<MenuNode[]>("/admin/menus")).data,
  saveMenu: async (payload: Omit<MenuNode, "id" | "children" | "access_level" | "access_source">, id?: number) =>
    (id ? await api.put<MenuNode>(`/admin/menus/${id}`, payload) : await api.post<MenuNode>("/admin/menus", payload)).data,
  moveMenu: async (id: number, payload: { parent_id: number | null; position: number }) =>
    (await api.patch<MenuNode>(`/admin/menus/${id}/move`, payload)).data,
  deleteMenu: async (id: number) => { await api.delete(`/admin/menus/${id}`); },
  grants: async (params: { role_id?: number; usuario_id?: number }) =>
    (await api.get<AccessGrant[]>("/access-grants", { params })).data,
  saveGrant: async (payload: {
    role_id: number | null;
    usuario_id: number | null;
    menu_id: number;
    access_level: AccessLevel;
    starts_at: string | null;
    ends_at: string | null;
    is_active: boolean;
  }) => (await api.put<AccessGrant>("/access-grants", payload)).data,
};
