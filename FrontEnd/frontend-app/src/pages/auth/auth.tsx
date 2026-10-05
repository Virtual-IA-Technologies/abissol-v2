import { useState } from "react";
import { ArrowRight, BrainCircuit, Eye, EyeOff, Lock, Mail, ShieldCheck, Sparkles } from "lucide-react";
import { useNavigate } from "react-router-dom";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useAuth } from "@/context/AuthContext";
import { usePlatformSettings } from "@/context/PlatformSettingsContext";
import { wolverineAPI } from "@/features/wolverine/api";
import { ForgotPasswordDialog } from "./forgot-password-dialog";

export default function AbissolAuth() {
  const navigate = useNavigate();
  const { login: authLogin } = useAuth();
  const { settings } = usePlatformSettings();
  const logo = settings.logo_dark_url || settings.logo_light_url || "/favicon.svg";
  const [showPassword, setShowPassword] = useState(false);
  const [rememberMe, setRememberMe] = useState(true);
  const [identificador, setIdentificador] = useState("");
  const [contrasena, setContrasena] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const handleLogin = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setLoading(true);
    setError("");
    try {
      const session = await wolverineAPI.login(identificador, contrasena, rememberMe);
      authLogin(session);
      navigate(session.usuario.requiere_cambio_clave ? "/cambiar-clave-obligatoria" : "/home", { replace: true });
    } catch (caught) {
      const status = (caught as { response?: { status?: number } }).response?.status;
      setError(status === 423 ? "Acceso bloqueado temporalmente. Intenta más tarde." : "Usuario o contraseña incorrectos");
    } finally {
      setLoading(false);
    }
  };

  return (
    <main className="relative min-h-screen overflow-hidden bg-[#06101f] text-white">
      <div className="absolute inset-0 bg-[radial-gradient(circle_at_15%_20%,rgba(37,99,235,.28),transparent_34%),radial-gradient(circle_at_85%_80%,rgba(6,182,212,.18),transparent_30%)]" />
      <div className="absolute inset-0 opacity-[.08] [background-image:linear-gradient(rgba(148,163,184,.5)_1px,transparent_1px),linear-gradient(90deg,rgba(148,163,184,.5)_1px,transparent_1px)] [background-size:44px_44px]" />
      <div className="relative mx-auto grid min-h-screen max-w-7xl lg:grid-cols-[1.08fr_.92fr]">
        <section className="hidden flex-col justify-between p-12 lg:flex xl:p-16">
          <div className="flex items-center gap-4">
            <div className="rounded-2xl border border-blue-300/20 bg-white/95 px-4 py-2 shadow-2xl shadow-blue-500/20">
              <img src={logo} alt={settings.app_title} className="h-20 w-auto object-contain" />
            </div>
            <div><p className="text-xl font-semibold tracking-tight">Versión 2</p><p className="text-xs uppercase tracking-[.24em] text-blue-200/60">{settings.organization_name}</p></div>
          </div>
          <div className="max-w-xl space-y-7">
            <div className="inline-flex items-center gap-2 rounded-full border border-cyan-300/20 bg-cyan-300/10 px-3 py-1.5 text-xs font-medium text-cyan-100"><Sparkles className="size-3.5" /> Nueva generación digital</div>
            <h1 className="text-5xl font-semibold leading-[1.08] tracking-[-.045em] xl:text-6xl">Gestión inteligente para una operación más segura.</h1>
            <p className="max-w-lg text-lg leading-8 text-slate-300">Una plataforma moderna, preparada para automatización, análisis e inteligencia artificial aplicada a los procesos ABISSOL.</p>
            <div className="grid grid-cols-2 gap-3 pt-3">
              <div className="rounded-2xl border border-white/10 bg-white/[.045] p-4 backdrop-blur"><BrainCircuit className="mb-3 size-5 text-cyan-300" /><p className="text-sm font-medium">Preparado para IA</p><p className="mt-1 text-xs text-slate-400">Arquitectura modular y escalable</p></div>
              <div className="rounded-2xl border border-white/10 bg-white/[.045] p-4 backdrop-blur"><ShieldCheck className="mb-3 size-5 text-blue-300" /><p className="text-sm font-medium">Control y auditoría</p><p className="mt-1 text-xs text-slate-400">Seguridad desde el núcleo</p></div>
            </div>
          </div>
          <p className="text-xs text-slate-500">{settings.footer_text}</p>
        </section>
        <section className="flex items-center justify-center p-5 sm:p-10 lg:p-14">
          <div className="w-full max-w-md rounded-[28px] border border-white/60 bg-white p-7 text-slate-900 shadow-[0_32px_100px_rgba(0,0,0,.38)] sm:p-10">
            <div className="mb-8 flex items-center gap-3 lg:hidden"><img src={settings.logo_light_url || "/favicon.svg"} alt={settings.app_title} className="size-12 object-contain" /><div><p className="font-semibold">{settings.app_title}</p><p className="text-xs text-slate-500">{settings.organization_name}</p></div></div>
            <div className="mb-8"><p className="mb-2 text-xs font-semibold uppercase tracking-[.18em] text-blue-600">Acceso seguro</p><h2 className="text-3xl font-semibold tracking-tight">Bienvenido</h2><p className="mt-2 text-sm leading-6 text-slate-500">Ingresa tus credenciales para continuar.</p></div>
            <form onSubmit={handleLogin} className="space-y-5">
              <div className="space-y-2"><Label htmlFor="identifier">Correo, usuario o teléfono</Label><div className="relative"><Mail className="absolute left-3.5 top-1/2 size-4 -translate-y-1/2 text-slate-400" /><Input id="identifier" type="text" required autoComplete="username" value={identificador} onChange={(event) => setIdentificador(event.target.value)} placeholder="correo, usuario o teléfono" className="h-12 rounded-xl border-slate-200 bg-slate-50 pl-10 focus-visible:ring-blue-500" /></div></div>
              <div className="space-y-2"><Label htmlFor="password">Contraseña</Label><div className="relative"><Lock className="absolute left-3.5 top-1/2 size-4 -translate-y-1/2 text-slate-400" /><Input id="password" type={showPassword ? "text" : "password"} required autoComplete="current-password" value={contrasena} onChange={(event) => setContrasena(event.target.value)} className="h-12 rounded-xl border-slate-200 bg-slate-50 px-10 focus-visible:ring-blue-500" /><button type="button" aria-label={showPassword ? "Ocultar contraseña" : "Mostrar contraseña"} onClick={() => setShowPassword(!showPassword)} className="absolute right-3.5 top-1/2 -translate-y-1/2 text-slate-400 hover:text-blue-600">{showPassword ? <EyeOff className="size-4" /> : <Eye className="size-4" />}</button></div></div>
              <div className="flex items-center justify-between gap-3"><label className="flex cursor-pointer items-center gap-2 text-sm text-slate-600">
                <input type="checkbox" checked={rememberMe} onChange={(event) => setRememberMe(event.target.checked)} className="size-4 rounded border-slate-300 text-blue-600" />
                Mantener sesión
              </label><ForgotPasswordDialog /></div>
              {error && <p className="rounded-xl bg-red-50 px-3 py-2 text-sm text-red-700">{error}</p>}
              <Button type="submit" disabled={loading} className="h-12 w-full rounded-xl bg-blue-600 text-white shadow-lg shadow-blue-600/20 hover:bg-blue-700">{loading ? "Verificando..." : "Ingresar"}<ArrowRight className="size-4" /></Button>
            </form>
            <p className="mt-7 text-center text-xs text-slate-400">Acceso monitoreado y protegido</p>
          </div>
        </section>
      </div>
    </main>
  );
}
