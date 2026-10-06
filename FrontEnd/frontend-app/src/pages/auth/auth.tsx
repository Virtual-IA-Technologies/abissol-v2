import { useState } from "react";
import { ArrowRight, Eye, EyeOff, Lock, Mail, ShieldCheck } from "lucide-react";
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
  const logo = settings.logo_light_url || "/abissol-logo.png";
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
    <main className="relative flex min-h-svh items-center justify-center overflow-hidden bg-[#101c19] px-4 py-10 text-slate-900 sm:py-12">
      <div aria-hidden="true" className="pointer-events-none absolute inset-0 bg-[radial-gradient(ellipse_at_12%_10%,rgba(116,154,64,.2),transparent_45%),radial-gradient(ellipse_at_90%_90%,rgba(64,119,75,.22),transparent_40%)]" />
      <div aria-hidden="true" className="pointer-events-none absolute inset-0 opacity-[.035] [background-image:linear-gradient(#b6c9b3_1px,transparent_1px),linear-gradient(90deg,#b6c9b3_1px,transparent_1px)] [background-size:48px_48px]" />
      <section aria-labelledby="login-title" className="relative w-full max-w-[440px] rounded-[28px] border border-white/70 bg-white px-6 py-8 shadow-[0_28px_90px_rgba(0,0,0,.3)] sm:px-10 sm:py-10">
        <header className="mb-8 text-center">
          <img src={logo} alt="ABISSOL — Asociación de Bienestar, Inclusión, Salud y Solidaridad" className="mx-auto mb-6 h-auto w-[180px] max-w-full object-contain" />
          <span className="inline-flex items-center gap-1.5 rounded-full bg-[#eff5e9] px-3 py-1 text-xs font-medium text-[#42652f]"><ShieldCheck className="size-3.5" aria-hidden="true" />Acceso seguro</span>
          <h1 id="login-title" className="mt-4 text-2xl font-semibold tracking-tight text-[#172d3e]">Bienvenido a ABISSOL</h1>
          <p className="mt-2 text-sm leading-6 text-slate-500">Ingresa tus credenciales para continuar.</p>
        </header>
        <form onSubmit={handleLogin} className="space-y-5">
          <div className="space-y-2">
            <Label htmlFor="identifier" className="text-xs font-medium text-slate-700">Correo, usuario o teléfono</Label>
            <div className="relative">
              <Mail aria-hidden="true" className="absolute left-3.5 top-1/2 size-4 -translate-y-1/2 text-slate-400" />
              <Input id="identifier" type="text" required autoComplete="username" value={identificador} onChange={(event) => setIdentificador(event.target.value)} placeholder="Correo, usuario o teléfono" className="h-12 rounded-xl border-slate-200 bg-white pl-10 text-slate-900 focus-visible:border-[#769e48] focus-visible:ring-[#769e48]/25" />
            </div>
          </div>
          <div className="space-y-2">
            <Label htmlFor="password" className="text-xs font-medium text-slate-700">Contraseña</Label>
            <div className="relative">
              <Lock aria-hidden="true" className="absolute left-3.5 top-1/2 size-4 -translate-y-1/2 text-slate-400" />
              <Input id="password" type={showPassword ? "text" : "password"} required autoComplete="current-password" value={contrasena} onChange={(event) => setContrasena(event.target.value)} className="h-12 rounded-xl border-slate-200 bg-white px-10 text-slate-900 focus-visible:border-[#769e48] focus-visible:ring-[#769e48]/25" />
              <button type="button" aria-label={showPassword ? "Ocultar contraseña" : "Mostrar contraseña"} aria-pressed={showPassword} onClick={() => setShowPassword(!showPassword)} className="absolute right-1 top-1/2 flex size-10 -translate-y-1/2 items-center justify-center rounded-lg text-slate-500 hover:text-[#42652f] focus-visible:outline-2 focus-visible:outline-[#769e48]">{showPassword ? <EyeOff className="size-4" /> : <Eye className="size-4" />}</button>
            </div>
          </div>
          <label className="flex w-fit cursor-pointer items-center gap-2 text-sm text-slate-600">
            <input type="checkbox" checked={rememberMe} onChange={(event) => setRememberMe(event.target.checked)} className="size-4 rounded border-slate-300 accent-[#527c35]" />
            Mantener sesión
          </label>
          {error && <p role="alert" className="rounded-xl bg-red-50 px-3 py-2 text-sm text-red-700">{error}</p>}
          <Button type="submit" disabled={loading} className="h-12 w-full rounded-xl border-0 bg-gradient-to-r from-[#507b30] to-[#397747] text-white shadow-lg shadow-[#527c35]/15 hover:from-[#426729] hover:to-[#2f633b] focus-visible:ring-[#769e48]/40">{loading ? "Verificando..." : "Ingresar"}<ArrowRight className="size-4" aria-hidden="true" /></Button>
          <div className="text-center"><ForgotPasswordDialog /></div>
        </form>
        <footer className="mt-7 border-t border-slate-100 pt-5 text-center text-xs text-slate-400">ABISSOL · Bienestar, inclusión, salud y solidaridad</footer>
      </section>
    </main>
  );
}
