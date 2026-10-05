import {
  Ambulance, Bell, BookOpen, Boxes, BriefcaseBusiness, Building2, Calculator, CalendarDays,
  Camera, Car, ChartNoAxesCombined, Circle, CircleDollarSign, ClipboardList, Clock3, Cog,
  ContactRound, Database, FileChartColumn, FileText, FolderKanban, GitBranch, GraduationCap,
  Hammer, HandCoins, HeartPulse, Hospital, KeyRound, Landmark, LayoutDashboard, LockKeyhole,
  Mail, MapPin, Menu, Package, Palette, Phone, Printer, ReceiptText, Search, Settings, Shield,
  ShieldAlert, ShieldCheck, ShoppingCart, Stethoscope, Truck, UserPlus, UserRoundCog, Users,
  WalletCards, Warehouse, Wrench,
  type LucideIcon,
} from "lucide-react";
import { LUCIDE_ICON_NAMES } from "@/lib/lucide-icon-names";

type IconName = (typeof LUCIDE_ICON_NAMES)[number];

export const MENU_ICONS: Array<{ name: string; label: string; icon: LucideIcon }> = [
  { name: "LayoutDashboard", label: "Panel", icon: LayoutDashboard },
  { name: "Users", label: "Usuarios", icon: Users },
  { name: "UserRoundCog", label: "Usuario", icon: UserRoundCog },
  { name: "Shield", label: "Escudo", icon: Shield },
  { name: "ShieldCheck", label: "Seguridad", icon: ShieldCheck },
  { name: "KeyRound", label: "Accesos", icon: KeyRound },
  { name: "Menu", label: "Menu", icon: Menu },
  { name: "Settings", label: "Sistema", icon: Settings },
  { name: "Cog", label: "Configuracion", icon: Cog },
  { name: "Palette", label: "Apariencia", icon: Palette },
  { name: "Mail", label: "Correo", icon: Mail },
  { name: "GitBranch", label: "DevOps", icon: GitBranch },
  { name: "Boxes", label: "Modulos", icon: Boxes },
  { name: "FolderKanban", label: "Carpeta", icon: FolderKanban },
  { name: "ClipboardList", label: "Lista", icon: ClipboardList },
  { name: "FileText", label: "Documento", icon: FileText },
  { name: "Database", label: "Base de datos", icon: Database },
  { name: "Building2", label: "Empresa", icon: Building2 },
  { name: "BriefcaseBusiness", label: "Gestion", icon: BriefcaseBusiness },
  { name: "WalletCards", label: "Cartera", icon: WalletCards },
  { name: "CircleDollarSign", label: "Finanzas", icon: CircleDollarSign },
  { name: "HandCoins", label: "Pagos", icon: HandCoins },
  { name: "ChartNoAxesCombined", label: "Reportes", icon: ChartNoAxesCombined },
  { name: "CalendarDays", label: "Calendario", icon: CalendarDays },
  { name: "Clock3", label: "Tiempo", icon: Clock3 },
  { name: "BookOpen", label: "Libro", icon: BookOpen },
  { name: "Bell", label: "Avisos", icon: Bell },
  { name: "Search", label: "Busqueda", icon: Search },
  { name: "LockKeyhole", label: "Protegido", icon: LockKeyhole },
  { name: "UserPlus", label: "Afiliaciones", icon: UserPlus },
  { name: "ContactRound", label: "Contactos", icon: ContactRound },
  { name: "ReceiptText", label: "Comprobantes", icon: ReceiptText },
  { name: "FileChartColumn", label: "Informe", icon: FileChartColumn },
  { name: "Calculator", label: "Calculos", icon: Calculator },
  { name: "Landmark", label: "Institucion", icon: Landmark },
  { name: "Warehouse", label: "Almacen", icon: Warehouse },
  { name: "Package", label: "Productos", icon: Package },
  { name: "ShoppingCart", label: "Compras", icon: ShoppingCart },
  { name: "Truck", label: "Transporte", icon: Truck },
  { name: "Car", label: "Vehiculo", icon: Car },
  { name: "Ambulance", label: "Ambulancia", icon: Ambulance },
  { name: "HeartPulse", label: "Salud", icon: HeartPulse },
  { name: "Stethoscope", label: "Medicina", icon: Stethoscope },
  { name: "Hospital", label: "Hospital", icon: Hospital },
  { name: "GraduationCap", label: "Capacitacion", icon: GraduationCap },
  { name: "MapPin", label: "Ubicacion", icon: MapPin },
  { name: "Phone", label: "Telefono", icon: Phone },
  { name: "Printer", label: "Impresion", icon: Printer },
  { name: "Camera", label: "Imagenes", icon: Camera },
  { name: "Wrench", label: "Herramientas", icon: Wrench },
  { name: "Hammer", label: "Operaciones", icon: Hammer },
  { name: "ShieldAlert", label: "Alertas", icon: ShieldAlert },
  { name: "Circle", label: "General", icon: Circle },
];

export const MENU_ICON_COMPONENTS = Object.fromEntries(
  MENU_ICONS.map((item) => [item.name, item.icon]),
) as Record<string, LucideIcon>;

export const ALL_MENU_ICON_NAMES = LUCIDE_ICON_NAMES;

export function normalizeMenuIconName(name: string | null | undefined): IconName | null {
  if (!name?.trim()) return null;
  const candidate = name.trim()
    .replace(/([a-z0-9])([A-Z])/g, "$1-$2")
    .replace(/[\s_]+/g, "-")
    .toLowerCase() as IconName;
  return (LUCIDE_ICON_NAMES as readonly string[]).includes(candidate) ? candidate : null;
}

export function menuIconExists(name: string | null | undefined) {
  return Boolean(name && (MENU_ICON_COMPONENTS[name] || normalizeMenuIconName(name)));
}

export const MENU_ICON_TONES = [
  "text-sky-700 medium:text-sky-300 dark:text-sky-300",
  "text-emerald-700 medium:text-emerald-300 dark:text-emerald-300",
  "text-violet-700 medium:text-violet-300 dark:text-violet-300",
  "text-amber-700 medium:text-amber-300 dark:text-amber-300",
  "text-rose-700 medium:text-rose-300 dark:text-rose-300",
  "text-cyan-700 medium:text-cyan-300 dark:text-cyan-300",
];

export function menuIconTone(seed: string) {
  const hash = [...seed].reduce((value, character) => value + character.charCodeAt(0), 0);
  return MENU_ICON_TONES[hash % MENU_ICON_TONES.length];
}
