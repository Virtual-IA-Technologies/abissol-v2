import { useState } from "react";
import { CheckCircle2, Mail } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Sheet, SheetBody, SheetContent, SheetDescription, SheetFooter, SheetHeader, SheetSection, SheetSectionDescription, SheetSectionTitle, SheetTitle, SheetTrigger } from "@/components/ui/sheet";
import { wolverineAPI } from "@/features/wolverine/api";
import { apiErrorMessage } from "@/lib/api-error";

export function ForgotPasswordDialog() {
  const [open, setOpen] = useState(false);
  const [correo, setCorreo] = useState("");
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      const response = await wolverineAPI.requestPasswordReset(correo.trim());
      setMessage(response.message);
    } catch (caught) {
      setError(apiErrorMessage(caught, "No se pudo solicitar el enlace"));
    } finally { setBusy(false); }
  };

  return <Sheet open={open} onOpenChange={(next) => { setOpen(next); if (!next) { setMessage(""); setError(""); } }}>
    <SheetTrigger asChild><button type="button" className="text-sm font-medium text-[#527c35] hover:text-[#3d5e28] hover:underline">¿Olvidaste tu contraseña?</button></SheetTrigger>
    <SheetContent className="w-full sm:max-w-lg"><SheetHeader><SheetTitle>Restablecer contraseña</SheetTitle><SheetDescription>Te enviaremos un enlace seguro al correo registrado en ABISSOL.</SheetDescription></SheetHeader>
      <SheetBody>{message ? <div className="flex gap-3 rounded-2xl border border-emerald-200 bg-emerald-50 p-5 text-sm leading-6 text-emerald-800 dark:border-emerald-900 dark:bg-emerald-950/40 dark:text-emerald-200"><CheckCircle2 className="mt-0.5 size-5 shrink-0" /><p>{message}</p></div> : <SheetSection><div><SheetSectionTitle>Correo de recuperación</SheetSectionTitle><SheetSectionDescription>Escribe el correo asociado a tu cuenta para recibir las instrucciones.</SheetSectionDescription></div><form id="forgot-password-form" onSubmit={submit} className="space-y-4"><div className="space-y-2"><Label htmlFor="reset-email">Correo electrónico</Label><div className="relative"><Mail className="absolute left-3.5 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" /><Input id="reset-email" type="email" required autoComplete="email" value={correo} onChange={(event) => setCorreo(event.target.value)} className="pl-10" placeholder="tu.correo@empresa.com" /></div></div>{error && <p className="rounded-xl border border-red-200 bg-red-50 p-3.5 text-sm leading-5 text-red-700 dark:border-red-900 dark:bg-red-950/40 dark:text-red-200">{error}</p>}</form></SheetSection>}</SheetBody>
      <SheetFooter>{message ? <Button onClick={() => setOpen(false)}>Entendido</Button> : <><Button type="button" variant="outline" onClick={() => setOpen(false)}>Cancelar</Button><Button type="submit" form="forgot-password-form" disabled={busy || !correo.trim()}>{busy ? "Enviando…" : "Enviar enlace"}</Button></>}</SheetFooter>
    </SheetContent>
  </Sheet>;
}
