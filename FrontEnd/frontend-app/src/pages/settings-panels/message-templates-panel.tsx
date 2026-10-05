import { useEffect, useState } from "react";
import { FileText, Pencil } from "lucide-react";
import { toast } from "sonner";

import { ActionButton } from "@/components/action-button";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Sheet, SheetBody, SheetContent, SheetDescription, SheetFooter, SheetHeader, SheetSection, SheetSectionDescription, SheetSectionTitle, SheetTitle } from "@/components/ui/sheet";
import { Textarea } from "@/components/ui/textarea";
import { useAuth } from "@/context/AuthContext";
import { settingsAPI } from "@/features/settings/api";
import type { MessageTemplateSettings, MessageTemplateSettingsWrite } from "@/features/settings/types";
import { apiErrorMessage } from "@/lib/api-error";

const variables = ["{nombre}", "{apellido}", "{usuario}", "{correo}", "{telefono}", "{clave_temporal}", "{organizacion}", "{url_acceso}"];

const empty: MessageTemplateSettingsWrite = {
  user_created_email_subject: "", user_created_email_body: "", user_created_whatsapp_body: "",
  password_reset_email_subject: "", password_reset_email_body: "", password_reset_whatsapp_body: "",
};

export default function MessageTemplatesPanel() {
  const { can } = useAuth();
  const [settings, setSettings] = useState<MessageTemplateSettings | null>(null);
  const [form, setForm] = useState<MessageTemplateSettingsWrite>(empty);
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);

  const accept = (next: MessageTemplateSettings) => {
    setSettings(next);
    const { id: _id, ...values } = next;
    void _id;
    setForm(values);
  };

  useEffect(() => {
    settingsAPI.getMessageTemplates().then(accept).catch((error) => toast.error(apiErrorMessage(error, "No se pudieron cargar las plantillas")));
  }, []);

  const save = async () => {
    setBusy(true);
    try {
      accept(await settingsAPI.updateMessageTemplates(form));
      setOpen(false);
      toast.success("Plantillas guardadas");
    } catch (error) {
      toast.error(apiErrorMessage(error, "No se pudieron guardar las plantillas"));
    } finally { setBusy(false); }
  };

  const complete = Object.values(form).every((value) => value.trim())
    && [form.user_created_email_body, form.user_created_whatsapp_body, form.password_reset_email_body, form.password_reset_whatsapp_body]
      .every((value) => value.includes("{clave_temporal}"));

  return <section className="space-y-5">
    <Card><CardHeader><CardTitle className="flex items-center gap-2"><FileText className="size-5" />Mensajes de credenciales</CardTitle><CardDescription>Textos usados al crear usuarios y restablecer contraseñas. La clave temporal nunca se guarda en Auditoría.</CardDescription></CardHeader><CardContent className="space-y-5">
      <div className="grid gap-4 lg:grid-cols-2">
        <TemplateSummary title="Usuario creado" subject={settings?.user_created_email_subject} email={settings?.user_created_email_body} whatsapp={settings?.user_created_whatsapp_body} />
        <TemplateSummary title="Contraseña restablecida" subject={settings?.password_reset_email_subject} email={settings?.password_reset_email_body} whatsapp={settings?.password_reset_whatsapp_body} />
      </div>
      {can("plantillas", "editor") && <ActionButton tone="edit" onClick={() => setOpen(true)}><Pencil className="size-4" />Editar plantillas</ActionButton>}
    </CardContent></Card>

    <Sheet open={open} onOpenChange={setOpen}><SheetContent className="w-full sm:max-w-2xl"><SheetHeader><SheetTitle>Editar plantillas</SheetTitle><SheetDescription>Configura mensajes breves. Cada cuerpo debe conservar la variable de clave temporal.</SheetDescription></SheetHeader><SheetBody className="space-y-7">
      <div className="flex flex-wrap gap-1.5">{variables.map((item) => <code key={item} className="rounded-md border bg-muted px-2 py-1 text-xs">{item}</code>)}</div>
      <TemplateFields prefix="user_created" title="Usuario creado" description="Se utiliza cuando el administrador crea una cuenta y elige uno o ambos canales." form={form} setForm={setForm} />
      <TemplateFields prefix="password_reset" title="Contraseña restablecida" description="Se utiliza desde la acción Restablecer contraseña de Usuarios." form={form} setForm={setForm} />
    </SheetBody><SheetFooter><Button variant="outline" onClick={() => setOpen(false)}>Cancelar</Button><ActionButton tone="edit" disabled={busy || !complete} onClick={save}>{busy ? "Guardando…" : "Guardar plantillas"}</ActionButton></SheetFooter></SheetContent></Sheet>
  </section>;
}

function TemplateSummary({ title, subject, email, whatsapp }: { title: string; subject?: string; email?: string; whatsapp?: string }) {
  return <div className="space-y-3 rounded-xl border bg-muted/15 p-4"><h3 className="font-semibold">{title}</h3><div><p className="text-xs font-medium text-muted-foreground">Asunto del correo</p><p className="text-sm">{subject || "Cargando…"}</p></div><div><p className="text-xs font-medium text-muted-foreground">Correo</p><p className="whitespace-pre-line text-sm text-muted-foreground">{email || "Cargando…"}</p></div><div><p className="text-xs font-medium text-muted-foreground">WhatsApp</p><p className="whitespace-pre-line text-sm text-muted-foreground">{whatsapp || "Cargando…"}</p></div></div>;
}

function TemplateFields({ prefix, title, description, form, setForm }: {
  prefix: "user_created" | "password_reset";
  title: string;
  description: string;
  form: MessageTemplateSettingsWrite;
  setForm: React.Dispatch<React.SetStateAction<MessageTemplateSettingsWrite>>;
}) {
  const subjectKey = `${prefix}_email_subject` as const;
  const emailKey = `${prefix}_email_body` as const;
  const whatsappKey = `${prefix}_whatsapp_body` as const;
  return <SheetSection><div><SheetSectionTitle>{title}</SheetSectionTitle><SheetSectionDescription>{description}</SheetSectionDescription></div><div className="space-y-5">
    <div className="space-y-2"><Label htmlFor={`${prefix}-subject`}>Asunto del correo</Label><Input id={`${prefix}-subject`} value={form[subjectKey]} onChange={(event) => setForm((current) => ({ ...current, [subjectKey]: event.target.value }))} /></div>
    <div className="space-y-2"><Label htmlFor={`${prefix}-email`}>Mensaje de correo</Label><Textarea id={`${prefix}-email`} className="min-h-40" value={form[emailKey]} onChange={(event) => setForm((current) => ({ ...current, [emailKey]: event.target.value }))} /></div>
    <div className="space-y-2"><Label htmlFor={`${prefix}-whatsapp`}>Mensaje de WhatsApp</Label><Textarea id={`${prefix}-whatsapp`} className="min-h-28" value={form[whatsappKey]} onChange={(event) => setForm((current) => ({ ...current, [whatsappKey]: event.target.value }))} /></div>
  </div></SheetSection>;
}
