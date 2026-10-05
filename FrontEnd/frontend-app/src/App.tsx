import { lazy, Suspense, type ReactNode } from "react";
import { Navigate, Route, Routes, useLocation } from "react-router-dom";

import { useAuth } from "./context/AuthContext";
import "./App.css";

const Auth = lazy(() => import("./pages/auth/auth"));
const ChangePasswordRequired = lazy(() => import("./pages/auth/change-password-required"));
const ResetPassword = lazy(() => import("./pages/auth/reset-password"));
const Home = lazy(() => import("./pages/home/home"));

function Authenticated({ children }: { children: ReactNode }) {
  const { token, user, loading } = useAuth();
  const location = useLocation();
  if (loading) return <Loading />;
  if (!token) return <Navigate to="/" replace />;
  if (user?.requiere_cambio_clave && location.pathname !== "/cambiar-clave-obligatoria") {
    return <Navigate to="/cambiar-clave-obligatoria" replace />;
  }
  return children;
}

function LoginRoute() {
  const { token, user, loading } = useAuth();
  if (loading) return <Loading />;
  if (!token) return <Auth />;
  return <Navigate to={user?.requiere_cambio_clave ? "/cambiar-clave-obligatoria" : "/inicio"} replace />;
}

function PasswordRoute() {
  const { token, user, loading } = useAuth();
  if (loading) return <Loading />;
  if (!token) return <Navigate to="/" replace />;
  if (!user?.requiere_cambio_clave) return <Navigate to="/inicio" replace />;
  return <ChangePasswordRequired />;
}

function Loading() {
  return (
    <div className="app-loading" role="status" aria-live="polite">
      <span className="app-loading-spinner" aria-hidden="true" />
      <span>Cargando</span>
    </div>
  );
}

export default function App() {
  return (
    <Suspense fallback={<Loading />}>
      <Routes>
        <Route path="/" element={<LoginRoute />} />
        <Route path="/cambiar-clave-obligatoria" element={<PasswordRoute />} />
        <Route path="/restablecer-clave" element={<ResetPassword />} />
        <Route path="/inicio" element={<Authenticated><Home dashboardOnly /></Authenticated>} />
        <Route
          path="/plataforma/*"
          element={
            <Authenticated>
              <Home />
            </Authenticated>
          }
        />

        <Route
          path="/documentos/*"
          element={
            <Authenticated>
              <Home documentsOnly />
            </Authenticated>
          }
        />
        <Route path="/home" element={<Navigate to="/inicio" replace />} />
        <Route path="/home/auditoria" element={<Navigate to="/plataforma/sistema/auditoria" replace />} />
        <Route path="/home/calendario" element={<Navigate to="/plataforma/sistema/calendario" replace />} />
        <Route path="/home/notificaciones" element={<Navigate to="/plataforma/sistema/notificaciones" replace />} />
        <Route path="/home/devops" element={<Navigate to="/plataforma/sistema/devops" replace />} />
        <Route path="/settings/users" element={<Navigate to="/plataforma/administracion/usuarios" replace />} />
        <Route path="/settings/roles" element={<Navigate to="/plataforma/administracion/roles" replace />} />
        <Route path="/settings/access" element={<Navigate to="/plataforma/administracion/accesos" replace />} />
        <Route path="/settings/menus" element={<Navigate to="/plataforma/sistema/menus" replace />} />
        <Route path="/settings/appearance" element={<Navigate to="/plataforma/sistema/configuracion/apariencia" replace />} />
        <Route path="/settings/smtp" element={<Navigate to="/plataforma/sistema/configuracion/smtp" replace />} />
        <Route path="/settings/whatsapp" element={<Navigate to="/plataforma/sistema/configuracion/whatsapp" replace />} />
        <Route path="/settings/templates" element={<Navigate to="/plataforma/sistema/configuracion/plantillas" replace />} />
        <Route path="/plataforma/sistema/apariencia" element={<Navigate to="/plataforma/sistema/configuracion/apariencia" replace />} />
        <Route path="/plataforma/sistema/smtp" element={<Navigate to="/plataforma/sistema/configuracion/smtp" replace />} />
        <Route path="/plataforma/sistema/whatsapp" element={<Navigate to="/plataforma/sistema/configuracion/whatsapp" replace />} />
        <Route path="*" element={<Navigate to="/inicio" replace />} />
      </Routes>
    </Suspense>
  );
}
