import { useEffect, useState } from "react";
import { CheckCircle2, Mail, Pencil, Send } from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { ActionButton } from "@/components/action-button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Sheet, SheetBody, SheetContent, SheetDescription, SheetFooter, SheetHeader, SheetSection, SheetSectionDescription, SheetSectionTitle, SheetTitle } from "@/components/ui/sheet";
import { Switch } from "@/components/ui/switch";
import { useAuth } from "@/context/AuthContext";
import { settingsAPI } from "@/features/settings/api";
import type { SmtpSettings, SmtpSettingsWrite } from "@/features/settings/types";
import { apiErrorMessage } from "@/lib/api-error";

const empty: SmtpSettingsWrite = {
  host: "", port: 587, username: "", password: "", from_email: "", from_name: "ABISSOL",
  use_tls: true, use_ssl: false, is_active: false,
};

export default function SmtpPanel() {
  const { can, user } = useAuth();
  const [settings, setSettings] = useState<SmtpSettings | null>(null);
  const [form, setForm] = useState<SmtpSettingsWrite>(empty);
  const [editOpen, setEditOpen] = useState(false);
  const [testOpen, setTestOpen] = useState(false);
  const [testEmail, setTestEmail] = useState(user?.correo ?? "");
  const [busy, setBusy] = useState(false);

  const accept = (next: SmtpSettings) => {
    setSettings(next);
    setForm({
      host: next.host ?? "", port: next.port, username: next.username ?? "", password: "",
      from_email: next.from_email ?? "", from_name: next.from_name,
      use_tls: next.use_tls, use_ssl: next.use_ssl, is_active: next.is_active,
    });
  };

  useEffect(() => {
    settingsAPI.getSmtp().then(accept).catch((error) => toast.error(apiErrorMessage(error, "No se pudo cargar SMTP")));
  }, []);

  const save = async () => {
    setBusy(true);
    try {
      accept(await settingsAPI.updateSmtp({ ...form, password: form.password?.trim() || null }));
      setEditOpen(false);
      toast.success("Configuración SMTP guardada");
    } catch (error) {
      toast.error(apiErrorMessage(error, "No se pudo guardar SMTP"));
    } finally { setBusy(false); }
  };

  const test = async () => {
    setBusy(true);
    try {
      await settingsAPI.testSmtp(testEmail.trim());
      setTestOpen(false);
      toast.success("Correo de prueba enviado");
    } catch (error) {
      toast.error(apiErrorMessage(error, "No se pudo enviar el correo de prueba"));
    } finally { setBusy(false); }
  };

  return <section className="space-y-5">
    <Card><CardHeader><CardTitle className="flex items-center gap-2"><Mail className="size-5" />Servidor de salida</CardTitle><CardDescription>La clave se conserva cifrada y nunca se devuelve al navegador.</CardDescription></CardHeader><CardContent className="space-y-5">
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <div><p className="text-xs text-muted-foreground">Estado</p><p className="font-medium">{settings?.is_active ? "Activo" : "Inactivo"}</p></div>
        <div><p className="text-xs text-muted-foreground">Servidor</p><p className="font-medium">{settings?.host ? `${settings.host}:${settings.port}` : "Sin configurar"}</p></div>
        <div><p className="text-xs text-muted-foreground">Remitente</p><p className="font-medium">{settings?.from_email || "Sin configurar"}</p></div>
        <div><p className="text-xs text-muted-foreground">Seguridad</p><p className="font-medium">{settings?.use_ssl ? "SSL" : settings?.use_tls ? "STARTTLS" : "Sin cifrado"}</p></div>
      </div>
      {settings?.password_configured && <p className="flex items-center gap-2 text-sm text-emerald-700"><CheckCircle2 className="size-4" />Clave SMTP configurada</p>}
      {can("smtp", "editor") && <div className="flex flex-wrap gap-2"><ActionButton tone="edit" onClick={() => setEditOpen(true)}><Pencil className="size-4" />Configurar</ActionButton><ActionButton tone="info" disabled={!settings?.is_active} onClick={() => setTestOpen(true)}><Send className="size-4" />Enviar prueba</ActionButton></div>}
    </CardContent></Card>

    <Sheet open={editOpen} onOpenChange={setEditOpen}><SheetContent className="w-full sm:max-w-2xl"><SheetHeader><SheetTitle>Configurar SMTP</SheetTitle><SheetDescription>Completa los datos entregados por tu proveedor de correo.</SheetDescription></SheetHeader>
      <SheetBody className="space-y-7">
        <SheetSection><div><SheetSectionTitle>Servidor y credenciales</SheetSectionTitle><SheetSectionDescription>Datos de conexión y autenticación proporcionados por el servicio de correo.</SheetSectionDescription></div><div className="grid gap-x-5 gap-y-5 sm:grid-cols-2">
          <div className="space-y-2"><Label htmlFor="smtp-host">Servidor</Label><Input id="smtp-host" value={form.host ?? ""} onChange={(event) => setForm({ ...form, host: event.target.value })} placeholder="smtp.office365.com" /></div>
          <div className="space-y-2"><Label htmlFor="smtp-port">Puerto</Label><Input id="smtp-port" type="number" min={1} max={65535} value={form.port} onChange={(event) => setForm({ ...form, port: Number(event.target.value) })} /></div>
          <div className="space-y-2"><Label htmlFor="smtp-user">Usuario SMTP</Label><Input id="smtp-user" autoComplete="off" value={form.username ?? ""} onChange={(event) => setForm({ ...form, username: event.target.value })} /></div>
          <div className="space-y-2"><Label htmlFor="smtp-password">Clave SMTP</Label><Input id="smtp-password" type="password" autoComplete="new-password" value={form.password ?? ""} onChange={(event) => setForm({ ...form, password: event.target.value })} placeholder={settings?.password_configured ? "Dejar vacío para conservarla" : "Ingresa la clave"} /></div>
        </div></SheetSection>
        <SheetSection><div><SheetSectionTitle>Identidad del remitente</SheetSectionTitle><SheetSectionDescription>Nombre y correo que verán los destinatarios de los mensajes.</SheetSectionDescription></div><div className="grid gap-x-5 gap-y-5 sm:grid-cols-2">
          <div className="space-y-2"><Label htmlFor="smtp-from-name">Nombre remitente</Label><Input id="smtp-from-name" value={form.from_name} onChange={(event) => setForm({ ...form, from_name: event.target.value })} /></div>
          <div className="space-y-2"><Label htmlFor="smtp-from-email">Correo remitente</Label><Input id="smtp-from-email" type="email" value={form.from_email ?? ""} onChange={(event) => setForm({ ...form, from_email: event.target.value })} /></div>
        </div></SheetSection>
        <SheetSection><div><SheetSectionTitle>Seguridad y disponibilidad</SheetSectionTitle><SheetSectionDescription>Selecciona el cifrado de la conexión y habilita el servicio cuando esté listo.</SheetSectionDescription></div><div className="grid gap-3 sm:grid-cols-2">
          <label className="flex items-center justify-between gap-4 rounded-xl border bg-muted/20 px-4 py-3.5 text-sm font-medium"><span>STARTTLS</span><Switch checked={form.use_tls} onCheckedChange={(value) => setForm({ ...form, use_tls: value, use_ssl: value ? false : form.use_ssl })} /></label>
          <label className="flex items-center justify-between gap-4 rounded-xl border bg-muted/20 px-4 py-3.5 text-sm font-medium"><span>SSL directo</span><Switch checked={form.use_ssl} onCheckedChange={(value) => setForm({ ...form, use_ssl: value, use_tls: value ? false : form.use_tls })} /></label>
          <label className="flex items-center justify-between gap-4 rounded-xl border bg-muted/20 px-4 py-3.5 text-sm font-medium sm:col-span-2"><span>Servicio activo</span><Switch checked={form.is_active} onCheckedChange={(value) => setForm({ ...form, is_active: value })} /></label>
        </div></SheetSection>
      </SheetBody>
      <SheetFooter><Button variant="outline" onClick={() => setEditOpen(false)}>Cancelar</Button><ActionButton tone="edit" disabled={busy || !form.host?.trim() || !form.from_email?.trim() || !form.from_name.trim()} onClick={save}>{busy ? "Guardando…" : "Guardar"}</ActionButton></SheetFooter>
    </SheetContent></Sheet>

    <Sheet open={testOpen} onOpenChange={setTestOpen}><SheetContent className="w-full sm:max-w-lg"><SheetHeader><SheetTitle>Enviar correo de prueba</SheetTitle><SheetDescription>Comprueba la conexión y las credenciales antes de habilitar otros envíos.</SheetDescription></SheetHeader><SheetBody><SheetSection><div><SheetSectionTitle>Destinatario</SheetSectionTitle><SheetSectionDescription>El resultado de la prueba se enviará a este correo.</SheetSectionDescription></div><div className="space-y-2"><Label htmlFor="smtp-test-email">Correo electrónico</Label><Input id="smtp-test-email" type="email" value={testEmail} onChange={(event) => setTestEmail(event.target.value)} /></div></SheetSection></SheetBody><SheetFooter><Button variant="outline" onClick={() => setTestOpen(false)}>Cancelar</Button><ActionButton tone="info" disabled={busy || !testEmail.trim()} onClick={test}><Send className="size-4" />{busy ? "Enviando…" : "Enviar prueba"}</ActionButton></SheetFooter></SheetContent></Sheet>
  </section>;
}
