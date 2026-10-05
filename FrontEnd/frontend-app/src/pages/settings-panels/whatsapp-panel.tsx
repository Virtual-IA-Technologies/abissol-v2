import { useEffect, useState } from "react";
import { CheckCircle2, MessageCircle, Pencil, Send } from "lucide-react";
import { toast } from "sonner";

import { ActionButton } from "@/components/action-button";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Sheet, SheetBody, SheetContent, SheetDescription, SheetFooter, SheetHeader, SheetSection, SheetSectionDescription, SheetSectionTitle, SheetTitle } from "@/components/ui/sheet";
import { Switch } from "@/components/ui/switch";
import { Textarea } from "@/components/ui/textarea";
import { useAuth } from "@/context/AuthContext";
import { settingsAPI } from "@/features/settings/api";
import type { WhatsappSettings, WhatsappSettingsWrite } from "@/features/settings/types";
import { apiErrorMessage } from "@/lib/api-error";

const empty: WhatsappSettingsWrite = {
  endpoint: "https://texas.wablas.com/api/send-message", country_code: "51", token: "", secret_key: "",
  otp_enabled: false, otp_expiration_seconds: 300, otp_resend_seconds: 60, otp_code_length: 6,
  otp_message: "Tu codigo de acceso a ABISSOL es {code}. Vence en {minutes} minutos.", is_active: false,
};

export default function WhatsappPanel() {
  const { can, user } = useAuth();
  const [settings, setSettings] = useState<WhatsappSettings | null>(null);
  const [form, setForm] = useState<WhatsappSettingsWrite>(empty);
  const [editOpen, setEditOpen] = useState(false);
  const [testOpen, setTestOpen] = useState(false);
  const [testPhone, setTestPhone] = useState(user?.telefono ?? "");
  const [testMessage, setTestMessage] = useState("Prueba de WhatsApp de ABISSOL");
  const [busy, setBusy] = useState(false);

  const accept = (next: WhatsappSettings) => {
    setSettings(next);
    setForm({
      endpoint: next.endpoint, country_code: next.country_code, token: "", secret_key: "",
      otp_enabled: next.otp_enabled, otp_expiration_seconds: next.otp_expiration_seconds,
      otp_resend_seconds: next.otp_resend_seconds, otp_code_length: next.otp_code_length,
      otp_message: next.otp_message, is_active: next.is_active,
    });
  };

  useEffect(() => {
    settingsAPI.getWhatsapp().then(accept).catch((error) => toast.error(apiErrorMessage(error, "No se pudo cargar WhatsApp")));
  }, []);

  const save = async () => {
    setBusy(true);
    try {
      accept(await settingsAPI.updateWhatsapp({ ...form, token: form.token?.trim() || null, secret_key: form.secret_key?.trim() || null }));
      setEditOpen(false);
      toast.success("Configuracion de WhatsApp y OTP guardada");
    } catch (error) { toast.error(apiErrorMessage(error, "No se pudo guardar WhatsApp")); }
    finally { setBusy(false); }
  };

  const test = async () => {
    setBusy(true);
    try {
      await settingsAPI.testWhatsapp(testPhone.trim(), testMessage.trim());
      setTestOpen(false);
      toast.success("Mensaje de prueba enviado");
    } catch (error) { toast.error(apiErrorMessage(error, "No se pudo enviar el mensaje de prueba")); }
    finally { setBusy(false); }
  };

  return <section className="space-y-5">
    <Card><CardHeader><CardTitle className="flex items-center gap-2"><MessageCircle className="size-5" />Proveedor de WhatsApp</CardTitle><CardDescription>Canal global para mensajes y codigos OTP. Las credenciales se cifran y nunca regresan al navegador.</CardDescription></CardHeader><CardContent className="space-y-5">
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <div><p className="text-xs text-muted-foreground">Estado</p><p className="font-medium">{settings?.is_active ? "Activo" : "Inactivo"}</p></div>
        <div><p className="text-xs text-muted-foreground">Proveedor</p><p className="font-medium">{settings?.provider === "wablas" ? "Wablas" : settings?.provider || "Sin configurar"}</p></div>
        <div><p className="text-xs text-muted-foreground">Codigo de pais</p><p className="font-medium">+{settings?.country_code || "51"}</p></div>
        <div><p className="text-xs text-muted-foreground">OTP</p><p className="font-medium">{settings?.otp_enabled ? "Habilitado" : "Deshabilitado"}</p></div>
      </div>
      {settings?.token_configured && settings?.secret_key_configured && <p className="flex items-center gap-2 text-sm text-emerald-700"><CheckCircle2 className="size-4" />Token y clave secreta configurados</p>}
      {can("whatsapp", "editor") && <div className="flex flex-wrap gap-2"><ActionButton tone="edit" onClick={() => setEditOpen(true)}><Pencil className="size-4" />Configurar</ActionButton><ActionButton tone="info" disabled={!settings?.is_active} onClick={() => setTestOpen(true)}><Send className="size-4" />Enviar prueba</ActionButton></div>}
    </CardContent></Card>

    <Sheet open={editOpen} onOpenChange={setEditOpen}><SheetContent className="w-full sm:max-w-2xl"><SheetHeader><SheetTitle>Configurar WhatsApp y OTP</SheetTitle><SheetDescription>Completa las credenciales de Wablas y las reglas del codigo de acceso.</SheetDescription></SheetHeader><SheetBody className="space-y-7">
      <SheetSection><div><SheetSectionTitle>Conexion segura</SheetSectionTitle><SheetSectionDescription>Admite el endpoint clásico /api/send-message y el v2. Token y clave se guardan separados, cifrados, y el backend forma la cabecera Authorization correcta.</SheetSectionDescription></div><div className="grid gap-x-5 gap-y-5 sm:grid-cols-2">
        <div className="space-y-2 sm:col-span-2"><Label htmlFor="wa-endpoint">Endpoint API</Label><Input id="wa-endpoint" value={form.endpoint} onChange={(event) => setForm({ ...form, endpoint: event.target.value })} /></div>
        <div className="space-y-2"><Label htmlFor="wa-token">Token Wablas</Label><Input id="wa-token" type="password" autoComplete="new-password" value={form.token ?? ""} onChange={(event) => setForm({ ...form, token: event.target.value })} placeholder={settings?.token_configured ? "Vacío conserva el token actual" : "Token sin la clave secreta"} /></div>
        <div className="space-y-2"><Label htmlFor="wa-secret">Secret Key Wablas</Label><Input id="wa-secret" type="password" autoComplete="new-password" value={form.secret_key ?? ""} onChange={(event) => setForm({ ...form, secret_key: event.target.value })} placeholder={settings?.secret_key_configured ? "Vacío conserva la clave actual" : "Clave ubicada después del punto"} /></div>
        <div className="space-y-2"><Label htmlFor="wa-country">Codigo de pais</Label><Input id="wa-country" inputMode="numeric" value={form.country_code} onChange={(event) => setForm({ ...form, country_code: event.target.value.replace(/\D/g, "") })} /></div>
        <label className="flex items-center justify-between gap-4 rounded-xl border bg-muted/20 px-4 py-3.5 text-sm font-medium"><span>Servicio activo</span><Switch checked={form.is_active} onCheckedChange={(value) => setForm({ ...form, is_active: value })} /></label>
      </div></SheetSection>
      <SheetSection><div><SheetSectionTitle>Codigo OTP</SheetSectionTitle><SheetSectionDescription>La plantilla debe contener {"{code}"}; {"{minutes}"} es opcional.</SheetSectionDescription></div><div className="grid gap-x-5 gap-y-5 sm:grid-cols-3">
        <label className="flex items-center justify-between gap-4 rounded-xl border bg-muted/20 px-4 py-3.5 text-sm font-medium sm:col-span-3"><span>Permitir inicio de sesion con OTP</span><Switch checked={form.otp_enabled} onCheckedChange={(value) => setForm({ ...form, otp_enabled: value })} /></label>
        <div className="space-y-2"><Label htmlFor="otp-length">Digitos</Label><Input id="otp-length" type="number" min={4} max={8} value={form.otp_code_length} onChange={(event) => setForm({ ...form, otp_code_length: Number(event.target.value) })} /></div>
        <div className="space-y-2"><Label htmlFor="otp-expiry">Vigencia (seg.)</Label><Input id="otp-expiry" type="number" min={30} max={3600} value={form.otp_expiration_seconds} onChange={(event) => setForm({ ...form, otp_expiration_seconds: Number(event.target.value) })} /></div>
        <div className="space-y-2"><Label htmlFor="otp-resend">Reenvio (seg.)</Label><Input id="otp-resend" type="number" min={10} max={600} value={form.otp_resend_seconds} onChange={(event) => setForm({ ...form, otp_resend_seconds: Number(event.target.value) })} /></div>
        <div className="space-y-2 sm:col-span-3"><Label htmlFor="otp-template">Plantilla OTP</Label><Textarea id="otp-template" rows={3} value={form.otp_message} onChange={(event) => setForm({ ...form, otp_message: event.target.value })} /></div>
      </div></SheetSection>
    </SheetBody><SheetFooter><Button variant="outline" onClick={() => setEditOpen(false)}>Cancelar</Button><ActionButton tone="edit" disabled={busy || !form.endpoint.trim() || !form.country_code || !form.otp_message.includes("{code}")} onClick={save}>{busy ? "Guardando..." : "Guardar"}</ActionButton></SheetFooter></SheetContent></Sheet>

    <Sheet open={testOpen} onOpenChange={setTestOpen}><SheetContent className="w-full sm:max-w-lg"><SheetHeader><SheetTitle>Enviar WhatsApp de prueba</SheetTitle><SheetDescription>Comprueba la conexion antes de usar este canal en notificaciones.</SheetDescription></SheetHeader><SheetBody><SheetSection><div><SheetSectionTitle>Destino y mensaje</SheetSectionTitle><SheetSectionDescription>Puedes ingresar un numero local; ABISSOL agregara el codigo de pais configurado.</SheetSectionDescription></div><div className="space-y-5"><div className="space-y-2"><Label htmlFor="wa-test-phone">Telefono</Label><Input id="wa-test-phone" inputMode="tel" value={testPhone} onChange={(event) => setTestPhone(event.target.value)} /></div><div className="space-y-2"><Label htmlFor="wa-test-message">Mensaje</Label><Textarea id="wa-test-message" rows={4} value={testMessage} onChange={(event) => setTestMessage(event.target.value)} /></div></div></SheetSection></SheetBody><SheetFooter><Button variant="outline" onClick={() => setTestOpen(false)}>Cancelar</Button><ActionButton tone="info" disabled={busy || !testPhone.trim() || !testMessage.trim()} onClick={test}><Send className="size-4" />{busy ? "Enviando..." : "Enviar prueba"}</ActionButton></SheetFooter></SheetContent></Sheet>
  </section>;
}
