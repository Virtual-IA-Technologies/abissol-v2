import { lazy, Suspense, useEffect, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { Bell, Eye, LogOut, Search, Undo2, UserRound } from "lucide-react";
import { toast } from "sonner";

import { getAvatarColor } from "@/components/avatar-color";
import { GlobalSearch } from "@/components/global-search";
import { CalendarQuickPopover } from "@/components/calendar-quick-popover";
const MyAccountSheet = lazy(() => import("@/components/my-account-sheet").then(module => ({default: module.MyAccountSheet})));
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { Button } from "@/components/ui/button";
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuLabel, DropdownMenuSeparator, DropdownMenuTrigger } from "@/components/ui/dropdown-menu";
import { Separator } from "@/components/ui/separator";
import { SidebarTrigger } from "@/components/ui/sidebar";
import { useAuth } from "@/context/AuthContext";
import type { MenuNode } from "@/features/wolverine/types";
import { useNotifications } from "@/features/notifications/notification-context";
import { avatarUrl } from "@/lib/avatar";
import { ThemeToggle } from "./theme-toggle";

function initials(name: string) {
  const words = name.trim().split(/\s+/).filter(Boolean);
  return words.length > 1 ? `${words[0][0]}${words[1][0]}`.toUpperCase() : words[0]?.slice(0, 2).toUpperCase() || "U";
}

function activeTrail(items: MenuNode[], pathname: string, parents: MenuNode[] = []): MenuNode[] {
  for (const item of items) {
    const trail = [...parents, item];
    const childTrail = activeTrail(item.children, pathname, trail);
    if (childTrail.length) return childTrail;
    if (item.ruta && (pathname === item.ruta || pathname.startsWith(`${item.ruta}/`))) return trail;
  }
  return [];
}

export function SiteHeader({ compactNavigation = false, topNavigation = false }: { compactNavigation?: boolean; topNavigation?: boolean }) {
  const location = useLocation();
  const navigate = useNavigate();
  const { user, menus, impersonation, leaveImpersonation, logout, can } = useAuth();
  const { unread } = useNotifications();
  const [searchOpen, setSearchOpen] = useState(false);
  const [accountOpen, setAccountOpen] = useState(false);
  const userName = user ? `${user.nombre} ${user.apellido}`.trim() : "Usuario";
  const breadcrumb = activeTrail(menus, location.pathname).filter((item) => item.tipo === "menu" || item.tipo === "submenu");

  useEffect(() => {
    const openSearch = (event: KeyboardEvent) => {
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "k") {
        event.preventDefault(); setSearchOpen(true);
      }
    };
    window.addEventListener("keydown", openSearch);
    return () => window.removeEventListener("keydown", openSearch);
  }, []);

  const leave = async () => {
    try {
      await leaveImpersonation();
      toast.success("Volviste a tu cuenta de Programador");
    } catch {
      toast.error("No se pudo finalizar la impersonación");
    }
  };

  return (
    <div className={`sticky z-40 shrink-0 bg-background/95 shadow-sm backdrop-blur supports-[backdrop-filter]:bg-background/85 ${topNavigation ? "top-0 md:top-14" : "top-0"}`}>
      {impersonation?.active && (
        <div className="flex min-h-10 items-center justify-center gap-3 bg-amber-100 px-4 py-2 text-sm text-amber-950">
          <Eye className="size-4" />
          Viendo como <strong>{impersonation.effective_user?.nombre} {impersonation.effective_user?.apellido}</strong>
          <Button size="sm" variant="outline" onClick={leave} className="h-7 border-amber-300 bg-white/70">
            <Undo2 className="size-3.5" /> Volver a mi usuario
          </Button>
        </div>
      )}
      <header className="flex h-(--header-height) items-center gap-2 border-b">
        <div className="flex w-full items-center gap-3 px-4 lg:px-6">
          <div className="flex min-w-0 items-center gap-2 md:shrink-0">
            <SidebarTrigger className={`-ml-1 ${compactNavigation ? "md:hidden" : ""}`} />
            <Separator orientation="vertical" className="mx-2 data-[orientation=vertical]:h-4" />
            <nav aria-label="Ruta actual" className="flex max-w-52 min-w-0 items-center gap-1.5 truncate text-xs font-normal text-muted-foreground lg:max-w-72">
              {breadcrumb.map((item, index) => <span key={item.id} className="contents"><span className={index === breadcrumb.length - 1 ? "truncate text-foreground/80" : "truncate"}>{item.nombre}</span>{index < breadcrumb.length - 1 && <span aria-hidden="true" className="text-border">/</span>}</span>)}
            </nav>
          </div>
          <GlobalSearch open={searchOpen} onOpenChange={setSearchOpen} />
          <div className="ml-auto flex shrink-0 items-center gap-1">
            {can("calendario") && <CalendarQuickPopover />}
            {can("notificaciones") && <button type="button" onClick={() => navigate("/plataforma/sistema/notificaciones")} aria-label={`Abrir notificaciones${unread ? `, ${unread} sin leer` : ""}`} title="Notificaciones" className="relative flex size-9 items-center justify-center rounded-md text-muted-foreground hover:bg-muted hover:text-foreground"><Bell className="size-4" />{unread > 0 && <span className="absolute right-0.5 top-0.5 flex min-w-4 items-center justify-center rounded-full bg-red-500 px-1 text-[9px] font-semibold leading-4 text-white">{unread > 99 ? "99+" : unread}</span>}</button>}
            <button type="button" data-global-search-trigger aria-expanded={searchOpen} onClick={() => setSearchOpen(true)} aria-label="Abrir búsqueda global" className="flex size-9 items-center justify-center rounded-md text-muted-foreground hover:bg-muted md:hidden"><Search className="size-4" /></button>
            <ThemeToggle />
            {user && <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <button type="button" aria-label="Abrir Mi cuenta" className="ml-1 flex size-9 items-center justify-center rounded-full p-0 outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2">
                  <Avatar className="size-8">
                    <AvatarImage src={avatarUrl(user.avatar_file)} alt={userName} className="object-cover" />
                    <AvatarFallback className={`${getAvatarColor(userName)} text-[10px] font-medium text-white`}>{initials(userName)}</AvatarFallback>
                  </Avatar>
                </button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end" className="w-64">
                <DropdownMenuLabel className="font-normal">
                  <span className="block truncate text-sm font-medium">{userName}</span>
                  <span className="block truncate text-xs text-muted-foreground">{user.correo}</span>
                </DropdownMenuLabel>
                <DropdownMenuSeparator />
                <DropdownMenuItem onSelect={() => setAccountOpen(true)}><UserRound />Mi cuenta</DropdownMenuItem>
                <DropdownMenuItem onSelect={() => void logout()}><LogOut />Cerrar sesión</DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>}
          </div>
        </div>
      </header>
      {accountOpen && <Suspense fallback={null}><MyAccountSheet open={accountOpen} onOpenChange={setAccountOpen} /></Suspense>}
    </div>
  );
}
