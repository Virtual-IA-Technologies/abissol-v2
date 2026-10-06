"use client";

import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Eye, EyeOff, Lock, ShieldCheck } from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { wolverineAPI } from "@/features/wolverine/api";
import { useAuth } from "@/context/AuthContext";
import { usePlatformSettings } from "@/context/PlatformSettingsContext";

export default function ChangePasswordRequired() {
  const navigate = useNavigate();
  const { user, logout } = useAuth();
  const { settings } = usePlatformSettings();
  const logo = settings.logo_light_url || "/abissol-logo.png";
  const [nuevaClave, setNuevaClave] = useState("");
  const [confirmarClave, setConfirmarClave] = useState("");
  const [showNuevaClave, setShowNuevaClave] = useState(false);
  const [showConfirmarClave, setShowConfirmarClave] = useState(false);
  const [loading, setLoading] = useState(false);

  const handleChangePassword = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!nuevaClave.trim() || !confirmarClave.trim()) {
      toast.error("Debes ingresar y confirmar la nueva contraseña");
      return;
    }
    if (nuevaClave !== confirmarClave) {
      toast.error("Las contraseñas no coinciden");
      return;
    }
    if (nuevaClave.length < 10 || !/[a-z]/.test(nuevaClave) || !/[A-Z]/.test(nuevaClave) || !/\d/.test(nuevaClave)) {
      toast.error("Usa al menos 10 caracteres, mayúscula, minúscula y número");
      return;
    }
    try {
      setLoading(true);
      await wolverineAPI.changePassword({ nueva_clave: nuevaClave, confirmar_clave: confirmarClave });
      toast.success("Contraseña actualizada correctamente. Vuelve a iniciar sesión.");
      logout();
      navigate("/", { replace: true });
    } catch (caught: unknown) {
      const error = caught as { response?: { data?: { detail?: string; message?: string } } };
      toast.error(error.response?.data?.detail || error.response?.data?.message || "No se pudo cambiar la contraseña");
    } finally {
      setLoading(false);
    }
  };

  const handleLogout = () => {
    logout();
    navigate("/", { replace: true });
  };

  const passwordField = (id: string, label: string, value: string, setter: (value: string) => void, visible: boolean, toggle: () => void) => (
    <div className="space-y-2">
      <Label htmlFor={id} className="text-xs font-medium text-slate-700">{label}</Label>
      <div className="relative">
        <Lock className="absolute left-3.5 top-1/2 size-4 -translate-y-1/2 text-slate-400" />
        <Input id={id} type={visible ? "text" : "password"} required autoComplete="new-password" aria-describedby="password-requirements" value={value} onChange={(event) => setter(event.target.value)} placeholder="••••••••" className="h-12 rounded-xl border-slate-200 bg-white px-10 text-slate-900 focus-visible:border-[#769e48] focus-visible:ring-[#769e48]/25" />
        <button type="button" aria-label={visible ? "Ocultar contraseña" : "Mostrar contraseña"} aria-pressed={visible} onClick={toggle} className="absolute right-1 top-1/2 flex size-10 -translate-y-1/2 items-center justify-center rounded-lg text-slate-500 hover:text-[#42652f] focus-visible:outline-2 focus-visible:outline-[#769e48]">{visible ? <EyeOff className="size-4" /> : <Eye className="size-4" />}</button>
      </div>
    </div>
  );

  return (
    <main className="relative flex min-h-svh items-center justify-center overflow-hidden bg-[#101c19] px-4 py-10 text-slate-900 sm:py-12">
      <div aria-hidden="true" className="pointer-events-none absolute inset-0 bg-[radial-gradient(ellipse_at_12%_10%,rgba(116,154,64,.2),transparent_45%),radial-gradient(ellipse_at_90%_90%,rgba(64,119,75,.22),transparent_40%)]" />
      <div aria-hidden="true" className="pointer-events-none absolute inset-0 opacity-[.035] [background-image:linear-gradient(#b6c9b3_1px,transparent_1px),linear-gradient(90deg,#b6c9b3_1px,transparent_1px)] [background-size:48px_48px]" />
        <section aria-labelledby="change-password-title" className="relative w-full max-w-[440px] rounded-[28px] border border-white/70 bg-white px-6 py-8 shadow-[0_28px_90px_rgba(0,0,0,.3)] sm:px-10 sm:py-10">
          <header className="text-center">
            <img src={logo} alt="ABISSOL — Asociación de Bienestar, Inclusión, Salud y Solidaridad" className="mx-auto mb-6 h-auto w-[180px] max-w-full object-contain" />
            <span className="inline-flex items-center gap-1.5 rounded-full bg-[#eff5e9] px-3 py-1 text-xs font-medium text-[#42652f]"><ShieldCheck className="size-3.5" aria-hidden="true" />Primer acceso</span>
            <h1 id="change-password-title" className="mt-4 text-2xl font-semibold tracking-tight text-[#172d3e]">Crea una nueva contraseña</h1>
            <p className="mt-2 text-sm leading-6 text-slate-500">Hola {user?.nombre || "usuario"}, reemplaza tu clave temporal antes de continuar.</p>
          </header>
          <form onSubmit={handleChangePassword} className="mt-8 space-y-5">
            {passwordField("nueva_clave", "Nueva contraseña", nuevaClave, setNuevaClave, showNuevaClave, () => setShowNuevaClave(!showNuevaClave))}
            {passwordField("confirmar_clave", "Confirmar contraseña", confirmarClave, setConfirmarClave, showConfirmarClave, () => setShowConfirmarClave(!showConfirmarClave))}
            <p id="password-requirements" className="text-xs leading-5 text-slate-500">Usa al menos 10 caracteres, una mayúscula, una minúscula y un número.</p>
            <Button type="submit" disabled={loading} className="h-12 w-full rounded-xl border-0 bg-gradient-to-r from-[#507b30] to-[#397747] text-white shadow-lg shadow-[#527c35]/15 hover:from-[#426729] hover:to-[#2f633b] focus-visible:ring-[#769e48]/40">{loading ? "Actualizando..." : "Guardar y continuar"}</Button>
            <Button type="button" variant="ghost" onClick={handleLogout} className="h-11 w-full text-[#527c35] hover:bg-[#eff5e9] hover:text-[#3d5e28]">Cerrar sesión</Button>
          </form>
          <footer className="mt-7 border-t border-slate-100 pt-5 text-center text-xs text-slate-400">ABISSOL · Bienestar, inclusión, salud y solidaridad</footer>
        </section>
    </main>
  );
}
