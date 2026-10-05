"use client";

import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { BrainCircuit, Eye, EyeOff, Lock, ShieldCheck } from "lucide-react";
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
  const logo = settings.logo_dark_url || settings.logo_light_url || "/favicon.svg";
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
      <Label htmlFor={id}>{label}</Label>
      <div className="relative">
        <Lock className="absolute left-3.5 top-1/2 size-4 -translate-y-1/2 text-slate-400" />
        <Input id={id} type={visible ? "text" : "password"} required autoComplete="new-password" value={value} onChange={(event) => setter(event.target.value)} placeholder="••••••••" className="h-12 rounded-xl border-slate-200 bg-slate-50 px-10 focus-visible:ring-blue-500" />
        <button type="button" aria-label={visible ? "Ocultar contraseña" : "Mostrar contraseña"} onClick={toggle} className="absolute right-3.5 top-1/2 -translate-y-1/2 text-slate-400 hover:text-blue-600">{visible ? <EyeOff className="size-4" /> : <Eye className="size-4" />}</button>
      </div>
    </div>
  );

  return (
    <main className="relative min-h-screen overflow-hidden bg-[#06101f] text-white">
      <div className="absolute inset-0 bg-[radial-gradient(circle_at_15%_20%,rgba(37,99,235,.28),transparent_34%),radial-gradient(circle_at_85%_80%,rgba(6,182,212,.18),transparent_30%)]" />
      <div className="relative mx-auto grid min-h-screen max-w-6xl items-center gap-14 px-5 py-10 lg:grid-cols-2 lg:px-12">
        <section className="hidden lg:block">
          <div className="mb-9 flex items-center gap-4"><div className="rounded-2xl bg-white px-4 py-2"><img src={logo} alt={settings.app_title} className="h-20 w-auto object-contain" /></div><div><p className="text-xl font-semibold">{settings.app_title}</p><p className="text-xs uppercase tracking-[.22em] text-blue-200/60">{settings.organization_name}</p></div></div>
          <h1 className="text-5xl font-semibold leading-tight tracking-[-.04em]">Tu seguridad activa la nueva experiencia.</h1>
          <p className="mt-5 max-w-lg text-lg leading-8 text-slate-300">Actualiza tu clave temporal para proteger tu identidad y acceder al nuevo núcleo inteligente de ABISSOL.</p>
          <div className="mt-8 flex gap-3"><div className="rounded-2xl border border-white/10 bg-white/5 p-4"><ShieldCheck className="size-5 text-cyan-300" /></div><div className="rounded-2xl border border-white/10 bg-white/5 p-4"><BrainCircuit className="size-5 text-blue-300" /></div></div>
        </section>
        <section className="rounded-[28px] border border-white/60 bg-white p-7 text-slate-900 shadow-[0_32px_100px_rgba(0,0,0,.38)] sm:p-10">
          <div className="mb-7 flex items-center gap-3 lg:hidden"><img src={settings.logo_light_url || "/favicon.svg"} alt={settings.app_title} className="size-12 object-contain" /><div><p className="font-semibold">{settings.app_title}</p><p className="text-xs text-slate-500">{settings.organization_name}</p></div></div>
          <p className="mb-2 text-xs font-semibold uppercase tracking-[.18em] text-blue-600">Primer acceso</p>
          <h2 className="text-3xl font-semibold tracking-tight">Crea una nueva contraseña</h2>
          <p className="mt-3 text-sm leading-6 text-slate-500">Hola {user?.nombre || "usuario"}, reemplaza tu clave temporal antes de continuar.</p>
          <form onSubmit={handleChangePassword} className="mt-8 space-y-5">
            {passwordField("nueva_clave", "Nueva contraseña", nuevaClave, setNuevaClave, showNuevaClave, () => setShowNuevaClave(!showNuevaClave))}
            {passwordField("confirmar_clave", "Confirmar contraseña", confirmarClave, setConfirmarClave, showConfirmarClave, () => setShowConfirmarClave(!showConfirmarClave))}
            <Button type="submit" disabled={loading} className="h-12 w-full rounded-xl bg-blue-600 text-white shadow-lg shadow-blue-600/20 hover:bg-blue-700">{loading ? "Actualizando..." : "Guardar y continuar"}</Button>
            <Button type="button" variant="ghost" onClick={handleLogout} className="h-11 w-full text-slate-500 hover:text-slate-900">Cerrar sesión</Button>
          </form>
        </section>
      </div>
    </main>
  );
}
