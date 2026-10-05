import { useEffect, useState } from "react";
import { Bot, CheckCircle2, Pencil, ShieldCheck, XCircle } from "lucide-react";
import { toast } from "sonner";

import { ActionButton } from "@/components/action-button";
import { SearchableSelect } from "@/components/searchable-select";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Sheet, SheetBody, SheetContent, SheetDescription, SheetFooter, SheetHeader, SheetSection, SheetSectionDescription, SheetSectionTitle, SheetTitle } from "@/components/ui/sheet";
import { Switch } from "@/components/ui/switch";
import { Textarea } from "@/components/ui/textarea";
import { useAuth } from "@/context/AuthContext";
import { settingsAPI } from "@/features/settings/api";
import type { AviConfiguration, AviSettings } from "@/features/settings/types";
import { apiErrorMessage } from "@/lib/api-error";

const providerOptions = [
  { value: "gemini", label: "Gemini" },
  { value: "groq", label: "Groq" },
  { value: "mistral", label: "Mistral" },
];
const severityOptions = [
  { value: "info", label: "Información y superiores" },
  { value: "warning", label: "Advertencias y críticas" },
  { value: "critical", label: "Solo críticas" },
];

function Toggle({ label, description, checked, onChange, disabled = false }: {
  label: string; description: string; checked: boolean; onChange: (value: boolean) => void; disabled?: boolean;
}) {
  return <label className="flex items-center justify-between gap-4 rounded-xl border bg-muted/15 px-4 py-3">
    <span><span className="block text-sm font-medium">{label}</span><span className="block text-xs leading-5 text-muted-foreground">{description}</span></span>
    <Switch checked={checked} disabled={disabled} onCheckedChange={onChange} />
  </label>;
}

export default function AviSettingsPanel() {
  const { can } = useAuth();
  const [record, setRecord] = useState<AviSettings | null>(null);
  const [form, setForm] = useState<AviConfiguration | null>(null);
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    settingsAPI.getAvi()
      .then((data) => { setRecord(data); setForm(data.settings); })
      .catch((error) => toast.error(apiErrorMessage(error, "No se pudo cargar AVI")));
  }, []);

  const save = async () => {
    if (!record || !form) return;
    setBusy(true);
    try {
      const next = await settingsAPI.updateAvi(record.revision, form);
      setRecord(next); setForm(next.settings); setOpen(false);
      toast.success("Configuración de AVI guardada");
    } catch (error) { toast.error(apiErrorMessage(error, "No se pudo guardar AVI")); }
    finally { setBusy(false); }
  };

  const updateProviderPriority = (index: number, provider: AviConfiguration["ai"]["providers"][number]) => {
    if (!form) return;
    const providers = form.ai.providers.filter((item) => item !== provider);
    providers.splice(Math.min(index, providers.length), 0, provider);
    setForm({ ...form, ai: { ...form.ai, providers } });
  };

  return (
    <section className="space-y-5">
      {/* Tarjeta de resumen */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2"><Bot className="size-5 text-violet-600" />Asistente virtual inteligente</CardTitle>
          <CardDescription>Parámetros globales y capacidades de AVI. Los permisos de cada opción continúan bajo Wolverine.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-5">
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <div><p className="text-xs text-muted-foreground">Estado</p><p className="font-medium">{record?.settings.enabled ? "Activo" : "Inactivo"}</p></div>
            <div><p className="text-xs text-muted-foreground">Nombre</p><p className="font-medium">{record?.settings.assistant_name || "AVI"}</p></div>
            <div><p className="text-xs text-muted-foreground">Iniciativa</p><p className="font-medium">{record?.settings.initiative.enabled ? "Habilitada" : "Deshabilitada"}</p></div>
            <div><p className="text-xs text-muted-foreground">IA externa</p><p className="font-medium">{record?.settings.ai.enabled ? record.settings.ai.providers.join(" → ") : "Deshabilitada"}</p></div>
          </div>
          {/* Indicador visual de estado de claves por proveedor */}
          {record && record.provider_status.length > 0 && (
            <div className="flex flex-wrap gap-3">
              {record.provider_status.map((ps) => (
                <span key={ps.provider} className={`inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-xs font-medium ${ps.configured ? "bg-emerald-50 text-emerald-700 dark:bg-emerald-950/30 dark:text-emerald-400" : "bg-muted text-muted-foreground"}`}>
                  {ps.configured ? <CheckCircle2 className="size-3.5" /> : <XCircle className="size-3.5" />}
                  {ps.provider} · {ps.model}
                </span>
              ))}
            </div>
          )}
          <p className="flex items-center gap-2 text-sm text-muted-foreground">
            <ShieldCheck className="size-4 text-emerald-600" />AVI usa el menú y los servicios autorizados; esta configuración no amplía accesos.
          </p>
          {can("avi-configuracion", "editor") && (
            <ActionButton tone="edit" onClick={() => setOpen(true)}><Pencil className="size-4" />Configurar AVI</ActionButton>
          )}
        </CardContent>
      </Card>

      {/* Panel de edición */}
      <Sheet open={open} onOpenChange={(value) => { if (!busy) setOpen(value); }}>
        <SheetContent className="w-full sm:max-w-3xl">
          <SheetHeader><SheetTitle>Configurar AVI</SheetTitle><SheetDescription>Activa capacidades gradualmente. Los proveedores externos requieren configuración segura del backend.</SheetDescription></SheetHeader>
          {form && (
            <SheetBody className="space-y-6">
              {/* Identidad */}
              <SheetSection>
                <div><SheetSectionTitle>Identidad y disponibilidad</SheetSectionTitle><SheetSectionDescription>Define cómo se presenta AVI y cuántos resultados muestra por consulta.</SheetSectionDescription></div>
                <div className="grid gap-4 sm:grid-cols-2">
                  <Toggle label="AVI activo" description="Muestra el asistente a los usuarios autenticados." checked={form.enabled} onChange={(enabled) => setForm({ ...form, enabled })} />
                  <div className="space-y-2"><Label htmlFor="avi-name">Nombre</Label><Input id="avi-name" maxLength={40} value={form.assistant_name} onChange={(e) => setForm({ ...form, assistant_name: e.target.value })} /></div>
                  <div className="space-y-2 sm:col-span-2"><Label htmlFor="avi-welcome">Mensaje de bienvenida</Label><Textarea id="avi-welcome" maxLength={300} rows={3} value={form.welcome_message} onChange={(e) => setForm({ ...form, welcome_message: e.target.value })} /></div>
                  <div className="space-y-2"><Label htmlFor="avi-results">Resultados máximos</Label><Input id="avi-results" type="number" min={3} max={20} value={form.max_results} onChange={(e) => setForm({ ...form, max_results: Number(e.target.value) })} /></div>
                </div>
              </SheetSection>

              {/* Capacidades */}
              <SheetSection>
                <div><SheetSectionTitle>Capacidades</SheetSectionTitle><SheetSectionDescription>Cada resultado sigue sujeto al permiso Wolverine y a la visibilidad del registro.</SheetSectionDescription></div>
                <div className="grid gap-3 sm:grid-cols-2">
                  {([
                    ["navigation", "Navegación", "Buscar y abrir opciones autorizadas."],
                    ["notifications", "Notificaciones", "Resumir avisos del buzón personal."],
                    ["documentation", "Documentación", "Consultar manuales visibles."],
                    ["document_management", "Manejo de archivos", "Buscar y abrir documentos autorizados."],
                    ["document_analysis", "Análisis documental", "Reservado para el motor trazable de análisis."],
                  ] as const).map(([key, label, description]) => (
                    <Toggle key={key} label={label} description={description} checked={form.capabilities[key]} onChange={(value) => setForm({
                      ...form,
                      capabilities: { ...form.capabilities, [key]: value },
                      ai: key === "document_analysis" && !value ? { ...form.ai, external_document_consent: false } : form.ai,
                    })} />
                  ))}
                </div>
              </SheetSection>

              {/* Iniciativa */}
              <SheetSection>
                <div><SheetSectionTitle>Iniciativa</SheetSectionTitle><SheetSectionDescription>Controla cuándo AVI puede adelantarse a informar sin realizar cambios operativos.</SheetSectionDescription></div>
                <div className="grid gap-4 sm:grid-cols-2">
                  <Toggle label="Iniciativa activa" description="Permite resúmenes y avisos proactivos." checked={form.initiative.enabled} onChange={(enabled) => setForm({ ...form, initiative: { ...form.initiative, enabled } })} />
                  <Toggle label="Resumen diario" description="Prepara una síntesis diaria de atención." checked={form.initiative.daily_summary} disabled={!form.initiative.enabled} onChange={(daily_summary) => setForm({ ...form, initiative: { ...form.initiative, daily_summary } })} />
                  <div className="space-y-2"><Label htmlFor="avi-summary-time">Hora del resumen</Label><Input id="avi-summary-time" type="time" disabled={!form.initiative.daily_summary} value={form.initiative.daily_summary_time} onChange={(e) => setForm({ ...form, initiative: { ...form.initiative, daily_summary_time: e.target.value } })} /></div>
                  <div className="space-y-2"><Label>Severidad mínima</Label><SearchableSelect options={severityOptions} value={form.initiative.minimum_severity} onValueChange={(v) => setForm({ ...form, initiative: { ...form.initiative, minimum_severity: v as AviConfiguration["initiative"]["minimum_severity"] } })} /></div>
                  <Toggle label="Horario silencioso" description="Evita iniciativa durante el intervalo; los avisos quedan en el buzón." checked={form.initiative.quiet_hours_enabled} onChange={(quiet_hours_enabled) => setForm({ ...form, initiative: { ...form.initiative, quiet_hours_enabled } })} />
                  <div className="grid grid-cols-2 gap-3">
                    <div className="space-y-2"><Label htmlFor="avi-quiet-start">Desde</Label><Input id="avi-quiet-start" type="time" disabled={!form.initiative.quiet_hours_enabled} value={form.initiative.quiet_hours_start} onChange={(e) => setForm({ ...form, initiative: { ...form.initiative, quiet_hours_start: e.target.value } })} /></div>
                    <div className="space-y-2"><Label htmlFor="avi-quiet-end">Hasta</Label><Input id="avi-quiet-end" type="time" disabled={!form.initiative.quiet_hours_enabled} value={form.initiative.quiet_hours_end} onChange={(e) => setForm({ ...form, initiative: { ...form.initiative, quiet_hours_end: e.target.value } })} /></div>
                  </div>
                  <div className="space-y-2"><Label htmlFor="avi-cooldown">Espera entre iniciativas (minutos)</Label><Input id="avi-cooldown" type="number" min={5} max={1440} value={form.initiative.cooldown_minutes} onChange={(e) => setForm({ ...form, initiative: { ...form.initiative, cooldown_minutes: Number(e.target.value) } })} /></div>
                </div>
              </SheetSection>

              {/* Proveedores IA */}
              <SheetSection>
                <div><SheetSectionTitle>Proveedores IA</SheetSectionTitle><SheetSectionDescription>AVI consulta ABISSOL primero y recurre a esta cadena solo si no obtiene una respuesta interna. Las claves permanecen en variables protegidas del servidor.</SheetSectionDescription></div>
                <div className="grid gap-4 sm:grid-cols-2">
                  <Toggle label="IA externa activa" description="Habilita el respaldo después de agotar la consulta interna." checked={form.ai.enabled} onChange={(enabled) => setForm({ ...form, ai: { ...form.ai, enabled, external_ai_consent: enabled ? form.ai.external_ai_consent : false, external_document_consent: enabled ? form.ai.external_document_consent : false } })} />
                  <Toggle label="Autorizar interpretación de preguntas" description="Permite enviar solo la pregunta cuando AVI necesita interpretarla. Los registros, archivos y el historial permanecen en ABISSOL." disabled={!form.ai.enabled} checked={form.ai.external_ai_consent} onChange={(external_ai_consent) => setForm({ ...form, ai: { ...form.ai, external_ai_consent, external_document_consent: false } })} />
                  <p className="text-xs text-muted-foreground sm:col-span-2">El análisis de archivos utiliza el índice interno. Los planes gratuitos y sus cuotas se administran en la cuenta de cada proveedor; configurar un modelo no garantiza gratuidad en una cuenta con facturación activa.</p>
                  {([0, 1, 2] as const).map((index) => (
                    <div key={index} className="space-y-2">
                      <Label>Prioridad {index + 1}</Label>
                      <SearchableSelect disabled={!form.ai.enabled} options={providerOptions} value={form.ai.providers[index] ?? ""} placeholder="Sin proveedor" onValueChange={(provider) => updateProviderPriority(index, provider as AviConfiguration["ai"]["providers"][number])} />
                    </div>
                  ))}
                  <div className="space-y-2"><Label htmlFor="avi-gemini-model">Modelo Gemini</Label><Input id="avi-gemini-model" disabled={!form.ai.enabled} value={form.ai.gemini_model} onChange={(e) => setForm({ ...form, ai: { ...form.ai, gemini_model: e.target.value } })} /></div>
                  <div className="space-y-2"><Label htmlFor="avi-groq-model">Modelo Groq</Label><Input id="avi-groq-model" disabled={!form.ai.enabled} value={form.ai.groq_model} onChange={(e) => setForm({ ...form, ai: { ...form.ai, groq_model: e.target.value } })} /></div>
                  <div className="space-y-2"><Label htmlFor="avi-mistral-model">Modelo Mistral</Label><Input id="avi-mistral-model" disabled={!form.ai.enabled} value={form.ai.mistral_model} onChange={(e) => setForm({ ...form, ai: { ...form.ai, mistral_model: e.target.value } })} /></div>
                  <div className="space-y-2"><Label htmlFor="avi-tokens">Salida máxima (tokens)</Label><Input id="avi-tokens" type="number" min={100} max={4000} disabled={!form.ai.enabled} value={form.ai.max_output_tokens} onChange={(e) => setForm({ ...form, ai: { ...form.ai, max_output_tokens: Number(e.target.value) } })} /></div>
                  <div className="space-y-2"><Label htmlFor="avi-history">Mensajes de contexto</Label><Input id="avi-history" type="number" min={2} max={20} disabled={!form.ai.enabled} value={form.ai.max_history_messages} onChange={(e) => setForm({ ...form, ai: { ...form.ai, max_history_messages: Number(e.target.value) } })} /></div>
                  <div className="space-y-2"><Label htmlFor="avi-timeout">Espera máxima (segundos)</Label><Input id="avi-timeout" type="number" min={5} max={60} disabled={!form.ai.enabled} value={form.ai.timeout_seconds} onChange={(e) => setForm({ ...form, ai: { ...form.ai, timeout_seconds: Number(e.target.value) } })} /></div>
                  {record && record.provider_status.length > 0 && (
                    <div className="space-y-2 sm:col-span-2">
                      <Label>Estado de claves en el servidor</Label>
                      <div className="flex flex-wrap gap-2">
                        {record.provider_status.map((ps) => (
                          <span key={ps.provider} className={`inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-xs font-medium ${ps.configured ? "bg-emerald-50 text-emerald-700 dark:bg-emerald-950/30 dark:text-emerald-400" : "bg-muted text-muted-foreground"}`}>
                            {ps.configured ? <CheckCircle2 className="size-3.5" /> : <XCircle className="size-3.5" />}
                            {ps.provider}: {ps.configured ? `clave configurada · ${ps.model}` : "sin clave"}
                          </span>
                        ))}
                      </div>
                      <p className="text-xs text-muted-foreground">
                        Las claves se configuran en las variables de entorno del servidor (<code>AVI_GEMINI_API_KEY</code>, <code>AVI_GROQ_API_KEY</code>, <code>AVI_MISTRAL_API_KEY</code>).
                      </p>
                    </div>
                  )}
                </div>
              </SheetSection>
            </SheetBody>
          )}
          <SheetFooter>
            <Button variant="outline" disabled={busy} onClick={() => setOpen(false)}>Cancelar</Button>
            <ActionButton tone="edit" disabled={busy || !form || form.assistant_name.trim().length < 2 || form.welcome_message.trim().length < 10} onClick={() => void save()}>
              {busy ? "Guardando…" : "Guardar configuración"}
            </ActionButton>
          </SheetFooter>
        </SheetContent>
      </Sheet>
    </section>
  );
}
