import { lazy, Suspense } from "react";
import { Navigate, Route, Routes, useLocation, useParams } from "react-router-dom";

import { AppSidebar } from "@/components/app-sidebar";
import { DesktopNavigation } from "@/components/navigation-layout";
import { SiteHeader } from "@/components/site-header";
import { AviAssistant } from "@/components/avi-assistant";
import { SidebarInset, SidebarProvider } from "@/components/ui/sidebar";
import { useAuth } from "@/context/AuthContext";
import { useTheme } from "@/context/theme-context";
import { AccessRoute } from "@/features/wolverine/access-route";
import { useIsMobile } from "@/hooks/use-mobile";
const ControlPanel = lazy(() => import("@/pages/home/control-panel"));
const MedicalPage = lazy(() => import("@/pages/medical/medical-page"));

const UsersPanel = lazy(() => import("@/pages/settings-panels/users-panel"));
const RolesPanel = lazy(() => import("@/pages/settings-panels/roles-panel"));
const MenusPanel = lazy(() => import("@/pages/settings-panels/menus-panel"));
const AccessPanel = lazy(() => import("@/pages/settings-panels/access-panel"));
const ConfigurationPage = lazy(() => import("@/pages/settings-panels/configuration-page"));
const AppearancePanel = lazy(() => import("@/pages/settings-panels/appearance-panel"));
const PersonalAppearancePage = lazy(() => import("@/pages/settings-panels/personal-appearance-page"));
const MessageTemplatesPanel = lazy(() => import("@/pages/settings-panels/message-templates-panel"));
const AviSettingsPanel = lazy(() => import("@/pages/settings-panels/avi-settings-panel"));
const AuditPage = lazy(() => import("@/pages/audit/audit-page"));
const DevopsPanel = lazy(() => import("@/pages/devops/devops-panel"));
const CalendarPage = lazy(() => import("@/pages/calendar/calendar-page"));
const NotificationsPage = lazy(() => import("@/pages/calendar/notifications-page"));
const DocumentationPage = lazy(() => import("@/features/documentation/page"));
const DocumentsPage = lazy(() => import("@/features/documents/page"));

export default function Home({
  dashboardOnly = false,
  documentsOnly = false,
}: {
  dashboardOnly?: boolean;
  documentsOnly?: boolean;
}) {
  const { menus } = useAuth();
  const { navigationLayout } = useTheme();
  const isMobile = useIsMobile();
  const showSidebar = navigationLayout === "sidebar" || isMobile;
  return <div className="min-h-screen"><SidebarProvider style={{ "--sidebar-width": "calc(var(--spacing) * 72)", "--header-height": "60px" } as React.CSSProperties}>
    {showSidebar && <AppSidebar />}
    {navigationLayout === "icons" && <DesktopNavigation layout="icons" items={menus} />}
    <SidebarInset className="min-w-0 overflow-x-clip">
    {navigationLayout === "top" && <DesktopNavigation layout="top" items={menus} />}
    <SiteHeader compactNavigation={navigationLayout !== "sidebar"} topNavigation={navigationLayout === "top"} />{dashboardOnly
      ? <Suspense fallback={<div className="p-6 text-sm text-muted-foreground">Cargando panel...</div>}><AccessRoute menu="inicio"><ControlPanel /></AccessRoute></Suspense>
      : <Suspense fallback={<div className="p-6 text-sm text-muted-foreground">Cargando modulo...</div>}>
        <Routes>
          {documentsOnly ? <>
            <Route path="archivos" element={<AccessRoute menu="documentos"><DocumentsPage /></AccessRoute>} />
            <Route path="*" element={<Navigate to="/documentos/archivos" replace />} />
          </> : <>
            <Route path="inicio" element={<Navigate to="/inicio" replace />} />
            <Route path="medical/plans" element={<AccessRoute menu="medical-plans"><Navigate to="/plataforma/medical/emissions?tab=plans" replace /></AccessRoute>} />
            <Route path="medical/dispatches" element={<AccessRoute menu="medical-dispatches"><Navigate to="/plataforma/medical/emissions?tab=dispatches" replace /></AccessRoute>} />
            {["network", "emissions", "liquidations", "billing", "reports"].map(section => <Route key={section} path={`medical/${section}`} element={<AccessRoute menu={section === "emissions" ? ["medical-emissions", "medical-plans", "medical-dispatches"] : `medical-${section}`}><MedicalPage key={section} section={section} /></AccessRoute>} />)}
            <Route path="administracion/usuarios" element={<AccessRoute menu="usuarios"><UsersPanel /></AccessRoute>} />
            <Route path="administracion/roles" element={<AccessRoute menu="roles"><RolesPanel /></AccessRoute>} />
            <Route path="administracion/accesos" element={<AccessRoute menu="accesos"><AccessPanel /></AccessRoute>} />
            <Route path="sistema/menus" element={<AccessRoute menu="menus"><MenusPanel /></AccessRoute>} />
            <Route path="seccion/:sectionSlug" element={<SectionIndex />} />
            <Route path="sistema/configuracion/general" element={<AccessRoute menu="general"><PersonalAppearancePage /></AccessRoute>} />
            <Route path="automatizacion/avi" element={<AccessRoute menu="avi-configuracion"><AviSettingsPanel /></AccessRoute>} />
            <Route path="sistema/configuracion/avi" element={<Navigate to="/plataforma/automatizacion/avi" replace />} />
            <Route path="sistema/configuracion" element={<ConfigurationPage />}>
              <Route index element={<ConfigurationIndex />} />
              <Route path="apariencia" element={<AccessRoute menu="apariencia"><AppearancePanel /></AccessRoute>} />
              <Route path="smtp" element={<AccessRoute menu="smtp"><Navigate to="/plataforma/medical/emissions?tab=settings&channel=email" replace /></AccessRoute>} />
              <Route path="whatsapp" element={<AccessRoute menu="whatsapp"><Navigate to="/plataforma/medical/emissions?tab=settings&channel=whatsapp" replace /></AccessRoute>} />
              <Route path="plantillas" element={<AccessRoute menu="plantillas"><MessageTemplatesPanel /></AccessRoute>} />
            </Route>
            <Route path="sistema/auditoria" element={<AccessRoute menu="auditoria"><AuditPage /></AccessRoute>} />
            <Route path="sistema/calendario" element={<AccessRoute menu="calendario"><CalendarPage /></AccessRoute>} />
            <Route path="sistema/notificaciones" element={<AccessRoute menu="notificaciones"><NotificationsPage /></AccessRoute>} />
            <Route path="sistema/documentacion" element={<AccessRoute menu="documentacion"><DocumentationPage /></AccessRoute>} />
            <Route path="sistema/documentos" element={<DocumentsRedirect />} />
            <Route path="sistema/devops" element={<AccessRoute menu="devops"><DevopsPanel /></AccessRoute>} />
            <Route path="*" element={<Navigate to="/inicio" replace />} />
          </>}
        </Routes>
      </Suspense>}</SidebarInset><AviAssistant />
  </SidebarProvider></div>;
}

function DocumentsRedirect() {
  const location = useLocation();
  return <Navigate to={`/documentos/archivos${location.search}${location.hash}`} replace />;
}

function ConfigurationIndex() {
  const { can } = useAuth();
  if (can("apariencia")) return <Navigate to="apariencia" replace />;
  if (can("plantillas")) return <Navigate to="plantillas" replace />;
  return <Navigate to="/inicio" replace />;
}

function SectionIndex() {
  const { sectionSlug } = useParams();
  const location = useLocation();
  const { menus } = useAuth();
  const findSection = (items: typeof menus): (typeof menus)[number] | undefined => {
    for (const item of items) {
      if (item.tipo === "seccion" && (item.slug === sectionSlug || item.ruta === location.pathname)) return item;
      const nested = findSection(item.children);
      if (nested) return nested;
    }
    return undefined;
  };
  const section = findSection(menus);
  const firstRoute = (items: typeof menus): string | null => {
    for (const item of items) {
      if (item.ruta && item.tipo !== "seccion" && item.tipo !== "modulo") return item.ruta;
      const nested = firstRoute(item.children);
      if (nested) return nested;
    }
    return null;
  };
  const route = section ? firstRoute(section.children) : null;
  if (route) return <Navigate to={route} replace />;
  return <main className="p-6 text-sm text-muted-foreground">Esta sección todavía no tiene opciones disponibles para tu acceso.</main>;
}
