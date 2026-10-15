import type * as React from "react";
import { Link } from "react-router-dom";

import { useAuth } from "@/context/AuthContext";
import { NavMain } from "@/components/nav-menus/nav-main";
import { NavUser } from "@/components/nav-menus/nav-user";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Sidebar, SidebarContent, SidebarFooter, SidebarHeader } from "@/components/ui/sidebar";
import { usePlatformSettings } from "@/context/PlatformSettingsContext";
import { SystemsChat } from "@/components/systems-chat";
import { avatarUrl } from "@/lib/avatar";

export function AppSidebar(props: React.ComponentProps<typeof Sidebar>) {
  const { user, menus } = useAuth();
  const { settings } = usePlatformSettings();
  const lightLogo = settings.logo_light_url || "/abissol-favicon.png";
  const darkLogo = settings.logo_dark_url || lightLogo;
  const showOrganization = settings.organization_name.trim().toLocaleLowerCase() !== settings.app_title.trim().toLocaleLowerCase();
  return (
    <Sidebar {...props}>
      <SidebarHeader className="h-(--header-height) shrink-0 justify-center border-b border-sidebar-border px-4 py-0">
        <Link to="/inicio" aria-label={`Ir a ${settings.app_title}`} className="flex min-w-0 items-center gap-3 rounded-md outline-none focus-visible:ring-2 focus-visible:ring-sidebar-ring">
          <img src={lightLogo} alt="Logo de ABISSOL" className="size-10 shrink-0 rounded-full bg-white p-0.5 object-contain medium:hidden dark:hidden" />
          <img src={darkLogo} alt="Logo de ABISSOL" className="hidden size-10 shrink-0 rounded-full bg-white p-0.5 object-contain medium:block dark:block" />
          <span className="flex min-w-0 flex-col leading-none">
            <strong className="truncate text-[15px] font-semibold tracking-[0.12em] text-sidebar-foreground">{settings.app_title.trim().toUpperCase() === "ABISSOL" ? <>ABIS<span className="text-[#547d35] medium:text-[#a2c779] dark:text-[#a2c779]">SOL</span></> : settings.app_title}</strong>
            <span className="mt-1.5 truncate text-[10px] font-normal text-sidebar-foreground/70">{showOrganization ? settings.organization_name : "Inclusión, salud y solidaridad"}</span>
          </span>
        </Link>
      </SidebarHeader>
      <SidebarContent className="overflow-hidden"><ScrollArea className="sidebar-navigation-scroll h-full py-2"><NavMain items={menus} /></ScrollArea></SidebarContent>
      {user && <SidebarFooter className="border-t border-sidebar-border p-3"><SystemsChat sidebar /><NavUser user={{ name: `${user.nombre} ${user.apellido}`, email: user.correo, avatar: avatarUrl(user.avatar_file) }} /></SidebarFooter>}
    </Sidebar>
  );
}
