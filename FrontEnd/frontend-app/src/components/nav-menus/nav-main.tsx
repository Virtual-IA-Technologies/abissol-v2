import { useEffect, useRef, useState } from "react";
import { ChevronRight, SquareArrowLeft } from "lucide-react";
import { Link, useLocation } from "react-router-dom";

import { MenuIcon } from "@/components/menu-icon";
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible";
import { SidebarGroup, SidebarGroupLabel, SidebarMenu, SidebarMenuButton, SidebarMenuItem, SidebarMenuSub, SidebarMenuSubButton, SidebarMenuSubItem } from "@/components/ui/sidebar";
import type { MenuNode } from "@/features/wolverine/types";

function hasActiveRoute(item: MenuNode, pathname: string): boolean {
  return Boolean(item.ruta && (pathname === item.ruta || pathname.startsWith(`${item.ruta}/`)))
    || item.children.some((child) => hasActiveRoute(child, pathname));
}

function reveal(element: HTMLElement | null, delay = 0) {
  window.setTimeout(() => {
    const viewport = element?.closest<HTMLElement>('[data-slot="scroll-area-viewport"]');
    if (!element || !viewport) return;
    const bounds = viewport.getBoundingClientRect();
    const target = element.getBoundingClientRect();
    const offset = target.top < bounds.top
      ? target.top - bounds.top
      : target.bottom > bounds.bottom ? target.bottom - bounds.bottom : 0;
    if (offset) viewport.scrollTo({
      top: viewport.scrollTop + offset,
      behavior: window.matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth",
    });
  }, delay);
}

function MenuEntry({ item, pathname, colorIndex }: { item: MenuNode; pathname: string; colorIndex: number }) {
  const isActive = hasActiveRoute(item, pathname);
  const [open, setOpen] = useState(isActive);
  const itemRef = useRef<HTMLLIElement>(null);
  const endRef = useRef<HTMLSpanElement>(null);
  useEffect(() => {
    if (!isActive) return;
    setOpen(true);
    reveal(itemRef.current, 220);
  }, [isActive, pathname]);
  if ((item.tipo === "seccion" || !item.children.length) && item.ruta) {
    return <SidebarMenuItem ref={itemRef}><SidebarMenuButton asChild isActive={isActive} tooltip={item.nombre}><Link to={item.ruta}><MenuIcon name={item.icono} seed={item.slug} colorIndex={colorIndex} /><span>{item.nombre}</span></Link></SidebarMenuButton></SidebarMenuItem>;
  }
  return <Collapsible asChild open={open} onOpenChange={(next) => { setOpen(next); if (next) reveal(endRef.current, 220); }} className="group/collapsible"><SidebarMenuItem ref={itemRef}>
    <CollapsibleTrigger asChild><SidebarMenuButton tooltip={item.nombre} className="font-medium"><MenuIcon name={item.icono} seed={item.slug} colorIndex={colorIndex} /><span>{item.nombre}</span><ChevronRight className="ml-auto size-4 transition-transform group-data-[state=open]/collapsible:rotate-90" /></SidebarMenuButton></CollapsibleTrigger>
    <CollapsibleContent><SidebarMenuSub>{item.children.map((child) => <SubmenuEntry key={child.id} item={child} pathname={pathname} />)}<span ref={endRef} aria-hidden="true" /></SidebarMenuSub></CollapsibleContent>
  </SidebarMenuItem></Collapsible>;
}

function SubmenuEntry({ item, pathname }: { item: MenuNode; pathname: string }) {
  const isActive = hasActiveRoute(item, pathname);
  const [open, setOpen] = useState(isActive);
  const itemRef = useRef<HTMLLIElement>(null);
  const endRef = useRef<HTMLSpanElement>(null);
  useEffect(() => {
    if (!isActive) return;
    setOpen(true);
    reveal(itemRef.current, 220);
  }, [isActive, pathname]);
  if (!item.children.length && item.ruta) {
    return <SidebarMenuSubItem ref={itemRef}><SidebarMenuSubButton asChild isActive={isActive} className={item.tipo === "pestana" ? "h-8 pl-5 text-xs" : "h-9"}><Link to={item.ruta}><span>{item.nombre}</span></Link></SidebarMenuSubButton></SidebarMenuSubItem>;
  }
  return <Collapsible asChild open={open} onOpenChange={(next) => { setOpen(next); if (next) reveal(endRef.current, 220); }} className="group/submenu"><SidebarMenuSubItem ref={itemRef}>
    <CollapsibleTrigger asChild><SidebarMenuSubButton className="h-9 font-medium"><span>{item.nombre}</span><ChevronRight className="ml-auto size-3.5 transition-transform group-data-[state=open]/submenu:rotate-90" /></SidebarMenuSubButton></CollapsibleTrigger>
    <CollapsibleContent><div className="ml-5 space-y-1 border-l pl-2 pt-1">{item.children.map((child) => <SidebarMenuSubButton key={child.id} asChild isActive={hasActiveRoute(child, pathname)} className="h-8 text-xs"><Link to={child.ruta ?? "#"}><span>{child.nombre}</span></Link></SidebarMenuSubButton>)}<span ref={endRef} aria-hidden="true" /></div></CollapsibleContent>
  </SidebarMenuSubItem></Collapsible>;
}

export function NavMain({ items }: { items: MenuNode[] }) {
  const { pathname } = useLocation();
  const sections = items.flatMap((item) => {
    const collect = (node: MenuNode): MenuNode[] => [
      ...(node.tipo === "seccion" ? [node] : []),
      ...node.children.flatMap(collect),
    ];
    return collect(item);
  });
  const activeSection = sections.find((section) => hasActiveRoute(section, pathname));
  if (activeSection) return <>
    <SidebarGroup className="px-3 pb-1 pt-2">
      <SidebarMenu><SidebarMenuItem><SidebarMenuButton asChild size="lg" tooltip="Volver al menú principal"><Link to="/inicio"><SquareArrowLeft className="text-teal-600 dark:text-teal-300" /><span className="font-medium">{activeSection.nombre}</span></Link></SidebarMenuButton></SidebarMenuItem></SidebarMenu>
    </SidebarGroup>
    {activeSection.children.filter((item) => item.tipo === "modulo").map((module) => <SidebarGroup key={module.id} className="px-3 py-2">
      <SidebarGroupLabel className="px-2 text-[10px] font-semibold uppercase tracking-[.14em] text-sidebar-foreground/45">{module.nombre}</SidebarGroupLabel>
      <SidebarMenu>{module.children.map((item, index) => <MenuEntry key={item.id} item={item} pathname={pathname} colorIndex={index} />)}</SidebarMenu>
    </SidebarGroup>)}
  </>;
  const topLevel = items.filter((item) => item.tipo !== "modulo");
  const modules = items.filter((item) => item.tipo === "modulo");
  return <>
    {topLevel.length > 0 && <SidebarGroup className="px-3 pb-1 pt-2">
      <SidebarMenu>{topLevel.map((item, index) => <MenuEntry key={item.id} item={item} pathname={pathname} colorIndex={index} />)}</SidebarMenu>
    </SidebarGroup>}
    {modules.map((module) => <SidebarGroup key={module.id} className="px-3 py-2">
    <SidebarGroupLabel className="px-2 text-[10px] font-semibold uppercase tracking-[.14em] text-sidebar-foreground/45">{module.nombre}</SidebarGroupLabel>
    <SidebarMenu>{module.ruta && <MenuEntry item={module} pathname={pathname} colorIndex={0} />}{module.children.map((item, index) => <MenuEntry key={item.id} item={item} pathname={pathname} colorIndex={index} />)}</SidebarMenu>
  </SidebarGroup>)}</>;
}
