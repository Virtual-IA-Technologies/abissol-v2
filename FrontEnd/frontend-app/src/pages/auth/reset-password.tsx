import { useState } from "react";
import { CheckCircle2, Lock } from "lucide-react";
import { Link, useSearchParams } from "react-router-dom";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { wolverineAPI } from "@/features/wolverine/api";
import { apiErrorMessage } from "@/lib/api-error";

export default function ResetPassword() {
  const [params] = useSearchParams();
  const token = params.get("token") ?? "";
  const [password, setPassword] = useState("");
  const [confirmation, setConfirmation] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [done, setDone] = useState(false);

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    setError("");
    if (password !== confirmation) { setError("Las contraseñas no coinciden"); return; }
    setBusy(true);
    try {
      await wolverineAPI.completePasswordReset({ token, nueva_clave: password, confirmar_clave: confirmation });
      setDone(true);
    } catch (caught) {
      setError(apiErrorMessage(caught, "No se pudo restablecer la contraseña"));
    } finally { setBusy(false); }
  };

  return <main className="flex min-h-screen items-center justify-center bg-slate-950 p-5"><Card className="w-full max-w-md">
    <CardHeader><CardTitle>{done ? "Contraseña actualizada" : "Crear nueva contraseña"}</CardTitle><CardDescription>{done ? "Ya puedes ingresar nuevamente a ABISSOL." : "Usa al menos 10 caracteres, mayúscula, minúscula y número."}</CardDescription></CardHeader>
    <CardContent>{done ? <div className="space-y-5"><div className="flex items-center gap-3 rounded-xl bg-emerald-50 p-4 text-emerald-800"><CheckCircle2 className="size-5" />El cambio se realizó correctamente.</div><Button asChild className="w-full"><Link to="/">Volver al inicio de sesión</Link></Button></div> : <form onSubmit={submit} className="space-y-4">
      {!token && <p className="rounded-lg bg-red-50 p-3 text-sm text-red-700">El enlace no contiene un token válido.</p>}
      <div className="space-y-2"><Label htmlFor="new-password">Nueva contraseña</Label><div className="relative"><Lock className="absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" /><Input id="new-password" className="pl-9" type="password" required minLength={10} autoComplete="new-password" value={password} onChange={(event) => setPassword(event.target.value)} /></div></div>
      <div className="space-y-2"><Label htmlFor="confirm-password">Confirmar contraseña</Label><Input id="confirm-password" type="password" required minLength={10} autoComplete="new-password" value={confirmation} onChange={(event) => setConfirmation(event.target.value)} /></div>
      {error && <p className="rounded-lg bg-red-50 p-3 text-sm text-red-700">{error}</p>}
      <Button className="w-full" disabled={busy || !token || password.length < 10 || confirmation.length < 10}>{busy ? "Actualizando…" : "Guardar nueva contraseña"}</Button><Button asChild variant="ghost" className="w-full"><Link to="/">Cancelar</Link></Button>
    </form>}</CardContent>
  </Card></main>;
}
