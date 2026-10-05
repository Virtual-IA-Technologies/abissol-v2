import { useEffect, useState, type ChangeEvent } from "react";
import { Image, Palette, Save } from "lucide-react";
import { toast } from "sonner";

import { ActionButton } from "@/components/action-button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useAuth } from "@/context/AuthContext";
import { usePlatformSettings } from "@/context/PlatformSettingsContext";
import type { PlatformSettingsWrite } from "@/features/settings/types";
import { apiErrorMessage } from "@/lib/api-error";

export default function AppearancePanel() {
  const { settings, update, uploadBranding } = usePlatformSettings();
  const { can } = useAuth();
  const [form, setForm] = useState<PlatformSettingsWrite>(settings);
  const [files, setFiles] = useState<{ logo_light?: File; logo_dark?: File; favicon?: File }>({});
  const [saving, setSaving] = useState(false);
  useEffect(() => setForm(settings), [settings]);

  const file = (key: keyof typeof files) => (event: ChangeEvent<HTMLInputElement>) => {
    setFiles((current) => ({ ...current, [key]: event.target.files?.[0] }));
  };
  const save = async () => {
    setSaving(true);
    try {
      await update(form);
      if (Object.values(files).some(Boolean)) await uploadBranding(files);
      setFiles({});
      toast.success("Configuración de la plataforma actualizada");
    } catch (error) {
      toast.error(apiErrorMessage(error, "No se pudo guardar la apariencia"));
    } finally {
      setSaving(false);
    }
  };

  return <section className="space-y-5">
    <Card><CardHeader><CardTitle className="flex items-center gap-2"><Palette className="size-5" />Plataforma</CardTitle><CardDescription>Identidad institucional compartida por todos los usuarios.</CardDescription></CardHeader><CardContent className="grid gap-5 md:grid-cols-2">
      <div className="space-y-2"><Label htmlFor="app-title">Título de la plataforma</Label><Input id="app-title" value={form.app_title} maxLength={120} onChange={(e) => setForm({ ...form, app_title: e.target.value })} /></div>
      <div className="space-y-2"><Label htmlFor="organization-name">Nombre de la institución</Label><Input id="organization-name" value={form.organization_name} maxLength={160} onChange={(e) => setForm({ ...form, organization_name: e.target.value })} /></div>
      <div className="space-y-2"><Label htmlFor="footer">Texto del pie de página</Label><Input id="footer" value={form.footer_text} maxLength={255} onChange={(e) => setForm({ ...form, footer_text: e.target.value })} /></div>
      <div className="space-y-2"><Label htmlFor="color">Color principal</Label><div className="flex gap-2"><Input id="color" type="color" className="w-16 p-1" value={form.primary_color} onChange={(e) => setForm({ ...form, primary_color: e.target.value })} /><Input value={form.primary_color} pattern="#[0-9a-fA-F]{6}" onChange={(e) => setForm({ ...form, primary_color: e.target.value })} /></div></div>
    </CardContent></Card>
    <Card><CardHeader><CardTitle className="flex items-center gap-2"><Image className="size-5" />Logos</CardTitle><CardDescription>PNG, JPG, WebP o ICO; máximo 4 MB por archivo.</CardDescription></CardHeader><CardContent className="grid gap-5 md:grid-cols-3">
      {([['logo_light', 'Logo para fondo claro', settings.logo_light_url], ['logo_dark', 'Logo para fondo oscuro', settings.logo_dark_url], ['favicon', 'Favicon', settings.favicon_url]] as const).map(([key, label, preview]) => <div key={key} className="space-y-2"><Label htmlFor={key}>{label}</Label>{preview && <img src={preview} alt={label} className="h-16 max-w-full rounded-md border bg-white object-contain p-2" />}<Input id={key} type="file" accept="image/png,image/jpeg,image/webp,image/x-icon" onChange={file(key)} /></div>)}
    </CardContent></Card>
    {can("apariencia", "editor") && <div className="flex justify-end"><ActionButton tone="edit" onClick={save} disabled={saving || !form.app_title.trim() || !form.organization_name.trim() || !form.footer_text.trim()}><Save className="size-4" />{saving ? "Guardando…" : "Guardar configuración"}</ActionButton></div>}
  </section>;
}
