export type AccessLevel = "none" | "lector" | "editor" | "gestor";
export type ThemeName = "light" | "medium" | "dark" | "virtualia" | "lady";
export type NavigationLayout = "sidebar" | "icons" | "top";
export interface ThemeAppearanceCustomization {
  menu_palette: "theme" | "custom";
  background_palette: "theme" | "custom";
  menu_color: string;
  menu_tone: number;
  background_color: string;
  background_tone: number;
}

export interface Role {
  id: number;
  nombre: string;
  prioridad: number;
  es_superusuario: boolean;
  is_active: boolean;
  is_default: boolean;
  user_ids: number[];
}

export interface User {
  id: number;
  nombre: string;
  apellido: string;
  username: string;
  correo: string;
  telefono: string | null;
  avatar_file: string | null;
  tema: ThemeName;
  menu_palette?: "theme" | "custom";
  background_palette?: "theme" | "custom";
  menu_color?: string;
  menu_tone?: number;
  background_color?: string;
  background_tone?: number;
  appearance_overrides?: Partial<Record<ThemeName, ThemeAppearanceCustomization>>;
  navigation_layout?: NavigationLayout;
  escala?: number;
  is_active: boolean;
  requiere_cambio_clave: boolean;
  fecha_finalizacion: string | null;
  deleted_at: string | null;
  roles: Role[];
  role_assignments: UserRoleAssignment[];
}

export interface CredentialNotificationResult {
  canal: "correo" | "whatsapp";
  solicitado: boolean;
  enviado: boolean;
  detalle: string;
}

export interface UserCreateResult extends User {
  notificaciones: CredentialNotificationResult[];
}

export interface UserPasswordResetResult {
  message: string;
  clave_temporal: string;
  requiere_cambio_clave: boolean;
  notificaciones: CredentialNotificationResult[];
}

export interface UserRoleAssignment {
  rol_id: number;
  is_permanent: boolean;
  starts_at: string | null;
  ends_at: string | null;
  is_active: boolean;
  rol: Role;
}

export interface UserRoleAssignmentWrite {
  rol_id: number;
  is_permanent: boolean;
  starts_at: string | null;
  ends_at: string | null;
}

export interface MenuNode {
  id: number;
  parent_id: number | null;
  nombre: string;
  slug: string;
  ruta: string | null;
  icono: string | null;
  tipo: "seccion" | "modulo" | "menu" | "submenu" | "pestana";
  orden: number;
  is_visible: boolean;
  is_active: boolean;
  access_level: AccessLevel | null;
  access_source: "superuser" | "user" | "role" | null;
  children: MenuNode[];
}

export interface Impersonation {
  active: boolean;
  session_id: number | null;
  actor: User | null;
  effective_user: User | null;
}

export interface WolverineSession {
  access_token: string;
  token_type: "bearer";
  usuario: User;
  requiere_cambio_clave: boolean;
  access: Record<string, AccessLevel>;
  menus: MenuNode[];
  impersonation: Impersonation;
}

export interface AccessGrant {
  id: number;
  role_id: number | null;
  usuario_id: number | null;
  menu_id: number;
  access_level: AccessLevel;
  starts_at: string | null;
  ends_at: string | null;
  is_active: boolean;
  created_by: number | null;
  updated_by: number | null;
  created_at: string;
  updated_at: string;
}

export interface GlobalSearchResult {
  id: string;
  source: string;
  kind: "option" | "record";
  title: string;
  subtitle: string;
  url: string;
}

export interface GlobalSearchResponse {
  query: string;
  results: GlobalSearchResult[];
  truncated: boolean;
}
