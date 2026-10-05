import { useEffect, useRef, useState } from "react";
import { SquareArrowLeft } from "lucide-react";
import { Link, useLocation } from "react-router-dom";

import { MenuIcon } from "@/components/menu-icon";
import { NavMain } from "@/components/nav-menus/nav-main";
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuLabel, DropdownMenuSeparator, DropdownMenuTrigger } from "@/components/ui/dropdown-menu";
import { ScrollArea } from "@/components/ui/scroll-area";
import { usePlatformSettings } from "@/context/PlatformSettingsContext";
import type { MenuNode, NavigationLayout } from "@/features/wolverine/types";

type RouteEntry = { item: MenuNode; trail: string[] };

function hasActiveRoute(item: MenuNode, pathname: string): boolean {
  return Boolean(item.ruta && (pathname === item.ruta || pathname.startsWith(`${item.ruta}/`)))
    || item.children.some((child) => hasActiveRoute(child, pathname));
}

function routesOf(item: MenuNode, trail: string[] = []): RouteEntry[] {
  if (item.tipo === "seccion" && item.ruta) return [{ item, trail }];
  if (!item.children.length && item.ruta) return [{ item, trail }];
  const nextTrail = item.tipo === "modulo" ? trail : [...trail, item.nombre];
  return item.children.flatMap((child) => routesOf(child, nextTrail));
}

function MenuDropdown({ item, colorIndex }: { item: MenuNode; colorIndex: number }) {
  const { pathname } = useLocation();
  const [open, setOpen] = useState(false);
  const closeTimer = useRef<number | null>(null);
  const entries = routesOf(item);
  const active = hasActiveRoute(item, pathname);
  const cancelClose = () => {
    if (closeTimer.current !== null) window.clearTimeout(closeTimer.current);
    closeTimer.current = null;
    setOpen(true);
  };
  const scheduleClose = () => {
    if (closeTimer.current !== null) window.clearTimeout(closeTimer.current);
    closeTimer.current = window.setTimeout(() => setOpen(false), 140);
  };
  useEffect(() => () => {
    if (closeTimer.current !== null) window.clearTimeout(closeTimer.current);
  }, []);
  if (item.ruta && (item.tipo === "seccion" || !item.children.length)) {
    return <Link to={item.ruta} title={item.nombre} aria-label={item.nombre} className={`inline-flex h-10 items-center gap-2 rounded-lg px-3 text-sm font-medium transition ${active ? "bg-sidebar-accent text-sidebar-accent-foreground" : "text-sidebar-foreground/75 hover:bg-sidebar-accent hover:text-sidebar-accent-foreground"}`}>
      <MenuIcon name={item.icono} seed={item.slug} colorIndex={colorIndex} /><span>{item.nombre}</span>
    </Link>;
  }
  return <DropdownMenu open={open} onOpenChange={setOpen}>
    <DropdownMenuTrigger asChild>
      <button type="button" title={`${item.nombre}: pasa el mouse para ver opciones`} aria-label={item.nombre} onMouseEnter={cancelClose} onMouseLeave={scheduleClose} onFocus={cancelClose} className={`inline-flex h-10 items-center gap-2 rounded-lg px-3 text-sm font-medium outline-none transition focus-visible:ring-2 focus-visible:ring-sidebar-ring ${active ? "bg-sidebar-accent text-sidebar-accent-foreground" : "text-sidebar-foreground/75 hover:bg-sidebar-accent hover:text-sidebar-accent-foreground"}`}>
        <MenuIcon name={item.icono} seed={item.slug} colorIndex={colorIndex} /><span>{item.nombre}</span>
      </button>
    </DropdownMenuTrigger>
    <DropdownMenuContent side="bottom" align="start" sideOffset={4} className="min-w-60" onMouseEnter={cancelClose} onMouseLeave={scheduleClose} onCloseAutoFocus={(event) => event.preventDefault()}>
      <DropdownMenuLabel>{item.nombre}</DropdownMenuLabel><DropdownMenuSeparator />
      {entries.map(({ item: entry, trail }) => <DropdownMenuItem key={entry.id} asChild><Link to={entry.ruta!} onClick={() => setOpen(false)} className="flex items-center gap-2"><MenuIcon name={entry.icono} seed={entry.slug} colorIndex={colorIndex} /><span className="min-w-0"><span className="block truncate">{entry.nombre}</span>{trail.length > 0 && <span className="block truncate text-[10px] text-muted-foreground">{trail.join(" · ")}</span>}</span></Link></DropdownMenuItem>)}
    </DropdownMenuContent>
  </DropdownMenu>;
}

export function DesktopNavigation({ layout, items }: { layout: NavigationLayout; items: MenuNode[] }) {
  const { pathname } = useLocation();
  const { settings } = usePlatformSettings();
  const [iconsExpanded, setIconsExpanded] = useState(false);
  if (layout === "sidebar") return null;
  const logo = settings.logo_dark_url || settings.logo_light_url || "/favicon.svg";
  const sections = items.flatMap((item) => {
    const collect = (node: MenuNode): MenuNode[] => [
      ...(node.tipo === "seccion" ? [node] : []),
      ...node.children.flatMap(collect),
    ];
    return collect(item);
  });
  const activeSection = sections.find((section) => hasActiveRoute(section, pathname));
  const navigationItems = activeSection
    ? activeSection.children.filter((item) => item.tipo === "modulo")
    : items;
  if (layout === "icons") return <aside
    onMouseEnter={() => setIconsExpanded(true)}
    onMouseLeave={() => setIconsExpanded(false)}
    onFocusCapture={() => setIconsExpanded(true)}
    onBlurCapture={(event) => { if (!event.currentTarget.contains(event.relatedTarget)) setIconsExpanded(false); }}
    onClick={(event) => { if ((event.target as HTMLElement).closest("a")) setIconsExpanded(false); }}
    className={`sticky top-0 z-50 hidden h-svh shrink-0 overflow-hidden border-r border-sidebar-border bg-sidebar text-sidebar-foreground shadow-sm transition-[width] duration-200 md:flex md:flex-col ${iconsExpanded ? "w-72" : "w-16"}`}
  >
    <div className={`flex h-(--header-height) shrink-0 items-center border-b border-sidebar-border ${iconsExpanded ? "gap-3 px-4" : "justify-center px-2"}`}>
      <Link to="/inicio" aria-label="Ir al inicio" className="flex size-10 shrink-0 items-center justify-center rounded-xl border border-sidebar-border bg-sidebar-accent/40"><img src={logo} alt="" className="size-7 object-contain" /></Link>
      {iconsExpanded && <span className="truncate text-sm font-semibold">{settings.app_title || "ABISSOL"}</span>}
    </div>
    {iconsExpanded ? <ScrollArea className="min-h-0 flex-1 py-2"><NavMain items={items} /></ScrollArea> : <nav aria-label="Navegación principal por iconos" className="flex min-h-0 flex-1 flex-col items-center gap-1.5 overflow-y-auto px-2 py-3">
      {activeSection && <span title="Sección activa" className="mb-1 flex size-10 items-center justify-center rounded-xl bg-sidebar-accent/55 text-sidebar-accent-foreground"><SquareArrowLeft className="size-5" /></span>}
      {navigationItems.map((item, index) => <span key={item.id} title={`${item.nombre}: pasa el mouse para abrir el menú`} className={`flex size-10 shrink-0 items-center justify-center rounded-xl transition ${hasActiveRoute(item, pathname) ? "bg-sidebar-accent text-sidebar-accent-foreground shadow-sm" : "text-sidebar-foreground/70"}`}><MenuIcon name={item.icono} seed={item.slug} colorIndex={index} /></span>)}
    </nav>}
    <div className={`mt-auto shrink-0 border-t border-sidebar-border p-2 ${iconsExpanded ? "w-full" : "mx-auto w-10 px-0"}`}>
      <Link to="/plataforma/sistema/configuracion/general" title="Apariencia" aria-label="Apariencia" className={`flex h-10 items-center rounded-xl transition ${iconsExpanded ? "gap-3 px-3" : "w-10 justify-center"} ${pathname.startsWith("/plataforma/sistema/configuracion/general") ? "bg-sidebar-accent text-sidebar-accent-foreground shadow-sm" : "text-sidebar-foreground/70 hover:bg-sidebar-accent hover:text-sidebar-accent-foreground"}`}><MenuIcon name="Palette" seed="apariencia" colorIndex={5} /><span className={iconsExpanded ? "whitespace-nowrap text-sm" : "sr-only"}>Apariencia</span></Link>
    </div>
  </aside>;
  return <nav aria-label="Navegación principal superior" className="sticky top-0 z-50 hidden min-h-14 shrink-0 items-center gap-1 overflow-x-auto border-b border-sidebar-border bg-sidebar px-4 text-sidebar-foreground md:flex lg:px-6">
    <Link to="/inicio" aria-label="Ir al inicio" className="mr-2 flex size-9 shrink-0 items-center justify-center rounded-lg border border-sidebar-border bg-sidebar-accent/40"><img src={logo} alt="" className="size-6 object-contain" /></Link>
    {activeSection && <Link to="/inicio" className="mr-2 inline-flex h-10 shrink-0 items-center gap-2 rounded-lg bg-sidebar-accent/55 px-3 text-sm font-medium text-sidebar-accent-foreground"><SquareArrowLeft className="size-4" /><span>{activeSection.nombre}</span></Link>}
    {navigationItems.map((item, index) => <MenuDropdown key={item.id} item={item} colorIndex={index} />)}
  </nav>;
}
