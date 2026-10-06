import { FileText, Palette, Settings } from "lucide-react";
import { NavLink, Outlet } from "react-router-dom";

import { useAuth } from "@/context/AuthContext";

const tabClassName = ({ isActive }: { isActive: boolean }) =>
  `-mb-px flex shrink-0 items-center justify-center gap-2 border-b-2 px-4 py-3 text-sm font-medium transition-colors ${
    isActive
      ? "border-sky-500 text-foreground"
      : "border-transparent text-muted-foreground hover:border-border hover:text-foreground"
  }`;

export default function ConfigurationPage() {
  const { can } = useAuth();

  return <main className="space-y-5 p-5 md:p-7">
    <div>
      <div className="flex items-center gap-2">
        <Settings className="size-6 text-sky-600" />
        <h1 className="text-2xl font-semibold tracking-tight">Configuración</h1>
      </div>
      <p className="mt-1 text-sm text-muted-foreground">Administra la identidad visual y las plantillas de cuentas de la plataforma.</p>
    </div>

    <nav className="flex w-full overflow-x-auto border-b [scrollbar-width:none] [&::-webkit-scrollbar]:hidden" aria-label="Secciones de configuración">
      {can("apariencia") && <NavLink to="/plataforma/sistema/configuracion/apariencia" className={tabClassName}>
        <Palette className="size-4" />
        <span className="truncate">Plataforma</span>
      </NavLink>}
      {can("plantillas") && <NavLink to="/plataforma/sistema/configuracion/plantillas" className={tabClassName}>
        <FileText className="size-4" />
        <span className="truncate">Plantillas</span>
      </NavLink>}
    </nav>

    <Outlet />
  </main>;
}
