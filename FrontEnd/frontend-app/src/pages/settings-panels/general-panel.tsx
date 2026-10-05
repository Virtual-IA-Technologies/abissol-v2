import {useEffect, useState} from 'react';
import {toast} from 'sonner';
import {ActionButton} from '@/components/action-button';
import {apiErrorMessage} from '@/lib/api-error';
import { Grid2X2, Heart, Moon, PanelLeft, PanelTop, Save, Sparkles, Sun, SunMedium } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useTheme, type BackgroundPalette, type MenuPalette, type Theme } from "@/context/theme-context";
import type { NavigationLayout } from "@/features/wolverine/types";

const themes = [
  { value: "light", label: "Light", icon: Sun },
  { value: "medium", label: "Medium", icon: SunMedium },
  { value: "dark", label: "Dark", icon: Moon },
  { value: "virtualia", label: "Virtual IA", icon: Sparkles },
  { value: "lady", label: "Lady", icon: Heart },
] as const;

const menuPalettes = [
  { value: "theme", label: "Según el tema", colors: "linear-gradient(135deg,var(--sidebar),var(--sidebar-accent))" },
  { value: "custom", label: "Personalizar", colors: "linear-gradient(135deg,var(--custom-menu-surface),var(--custom-menu-color))" },
] as const;

const backgroundPalettes = [
  { value: "theme", label: "Según el tema", colors: "linear-gradient(135deg,var(--background),var(--muted))" },
  { value: "custom", label: "Personalizar", colors: "var(--custom-background-surface)" },
] as const;

const navigationLayouts = [
  { value: "sidebar", label: "Menú lateral", description: "Vista completa actual", icon: PanelLeft },
  { value: "icons", label: "Menú en iconos", description: "Barra compacta desplegable", icon: Grid2X2 },
  { value: "top", label: "Menú superior", description: "Navegación horizontal", icon: PanelTop },
] as const;

export default function GeneralPanel() {
  const { theme, applyTheme, menuPalette, applyMenuPalette, backgroundPalette, applyBackgroundPalette, menuColor, applyMenuColor, menuTone, applyMenuTone, backgroundColor, applyBackgroundColor, backgroundTone, applyBackgroundTone, scale, applyScale, navigationLayout, applyNavigationLayout, savePreferences } = useTheme();
  const [saving,setSaving]=useState(false);
  const [menuHex,setMenuHex]=useState(menuColor.toUpperCase());
  const [backgroundHex,setBackgroundHex]=useState(backgroundColor.toUpperCase());
  useEffect(()=>setMenuHex(menuColor.toUpperCase()),[menuColor]);
  useEffect(()=>setBackgroundHex(backgroundColor.toUpperCase()),[backgroundColor]);
  return <section data-slot="card" className="max-w-4xl space-y-7 rounded-xl border bg-card p-5 text-card-foreground">
    <div><h2 className="font-medium">Tu espacio de trabajo</h2><p className="mt-1 text-sm text-muted-foreground">Estos ajustes son personales. Revisa los cambios y guarda tu configuración para conservarla al volver a entrar.</p></div>
    <div className="space-y-3"><Label>Tema</Label><div className="flex flex-wrap gap-2" role="group" aria-label="Tema personal">
      {themes.map(({ value, label, icon: Icon }) => <Button key={value} disabled={saving} variant={theme === value ? "secondary" : "outline"} aria-pressed={theme === value} onClick={() => applyTheme(value as Theme)}><Icon className="size-4" />{label}</Button>)}
    </div><p className="text-xs text-muted-foreground">Se guarda en tu perfil.</p></div>
    <div className="space-y-3"><Label>Vista de navegación</Label><div className="grid gap-3 sm:grid-cols-3" role="group" aria-label="Vista personal de navegación">
      {navigationLayouts.map(({ value, label, description, icon: Icon }) => <button type="button" key={value} disabled={saving} aria-pressed={navigationLayout === value} onClick={() => applyNavigationLayout(value as NavigationLayout)} className={`group rounded-xl border p-3 text-left transition hover:-translate-y-0.5 hover:bg-accent ${navigationLayout === value ? "border-primary bg-accent ring-1 ring-primary/30" : "bg-background"}`}><span className="mb-3 flex h-16 items-center justify-center rounded-lg border bg-muted/50"><Icon className={`size-7 ${navigationLayout === value ? "text-primary" : "text-muted-foreground"}`} /></span><span className="block text-sm font-medium">{label}</span><span className="mt-1 block text-xs text-muted-foreground">{description}</span></button>)}
    </div><p className="text-xs text-muted-foreground">La vista cambia de inmediato para que puedas probarla; pulsa Guardar configuración para conservarla en otros equipos. En móvil se mantiene el menú desplegable.</p></div>
    <div className="grid gap-6 md:grid-cols-2">
      <div className="space-y-3"><Label>Paleta del menú</Label><div className="grid gap-2" role="group" aria-label="Paleta personal del menú">
        {menuPalettes.map((option) => <button type="button" key={option.value} disabled={saving} aria-pressed={menuPalette === option.value} onClick={() => applyMenuPalette(option.value as MenuPalette)} className={`flex items-center gap-3 rounded-lg border px-3 py-2 text-left text-sm transition hover:bg-accent ${menuPalette === option.value ? "border-primary bg-accent ring-1 ring-primary/30" : "bg-background"}`}><span className="h-7 w-12 shrink-0 rounded-md border" style={{ background: option.colors }} /><span>{option.label}{option.value === "custom" && <span className="ml-2 font-mono text-xs text-muted-foreground">{menuColor.toUpperCase()}</span>}</span></button>)}
      </div>{menuPalette === "custom" && <div className="space-y-3 rounded-lg border bg-background/70 p-3"><div className="flex gap-2"><Input aria-label="Selector de color del menú" type="color" className="w-14 shrink-0 p-1" value={menuColor} onChange={(event)=>applyMenuColor(event.target.value)} /><Input aria-label="Código hexadecimal del menú" value={menuHex} maxLength={7} onChange={(event)=>{const next=event.target.value.toUpperCase();setMenuHex(next);if(/^#[0-9A-F]{6}$/.test(next))applyMenuColor(next);}} onBlur={()=>setMenuHex(menuColor.toUpperCase())} /></div><div><div className="mb-1 flex justify-between text-xs text-muted-foreground"><span>Más oscuro</span><span>Tonalidad {menuTone}%</span><span>Más claro</span></div><Input aria-label="Tonalidad del menú" type="range" min={0} max={100} value={menuTone} onChange={(event)=>applyMenuTone(Number(event.target.value))} /></div></div>}<p className="text-xs text-muted-foreground">Cambia únicamente la navegación.</p></div>
      <div className="space-y-3"><Label>Paleta del fondo</Label><div className="grid gap-2" role="group" aria-label="Paleta personal del fondo">
        {backgroundPalettes.map((option) => <button type="button" key={option.value} disabled={saving} aria-pressed={backgroundPalette === option.value} onClick={() => applyBackgroundPalette(option.value as BackgroundPalette)} className={`flex items-center gap-3 rounded-lg border px-3 py-2 text-left text-sm transition hover:bg-accent ${backgroundPalette === option.value ? "border-primary bg-accent ring-1 ring-primary/30" : "bg-background"}`}><span className="h-7 w-12 shrink-0 rounded-md border" style={{ background: option.colors }} /><span>{option.label}{option.value === "custom" && <span className="ml-2 font-mono text-xs text-muted-foreground">{backgroundColor.toUpperCase()}</span>}</span></button>)}
      </div>{backgroundPalette === "custom" && <div className="space-y-3 rounded-lg border bg-background/70 p-3"><div className="flex gap-2"><Input aria-label="Selector de color del fondo" type="color" className="w-14 shrink-0 p-1" value={backgroundColor} onChange={(event)=>applyBackgroundColor(event.target.value)} /><Input aria-label="Código hexadecimal del fondo" value={backgroundHex} maxLength={7} onChange={(event)=>{const next=event.target.value.toUpperCase();setBackgroundHex(next);if(/^#[0-9A-F]{6}$/.test(next))applyBackgroundColor(next);}} onBlur={()=>setBackgroundHex(backgroundColor.toUpperCase())} /></div><div><div className="mb-1 flex justify-between text-xs text-muted-foreground"><span>Más oscuro</span><span>Tonalidad {backgroundTone}%</span><span>Más claro</span></div><Input aria-label="Tonalidad del fondo" type="range" min={0} max={100} value={backgroundTone} onChange={(event)=>applyBackgroundTone(Number(event.target.value))} /></div></div>}<p className="text-xs text-muted-foreground">Adapta el matiz del área de trabajo y calcula automáticamente un texto legible.</p></div>
    </div>
    <div className="space-y-3"><div className="flex items-center justify-between gap-3"><Label htmlFor="personal-scale">Escala de interfaz: {scale}%</Label><Button variant="ghost" size="sm" disabled={saving || scale === 100} onClick={() => applyScale(100)}>Restablecer</Button></div>
      <Input id="personal-scale" disabled={saving} type="range" min={80} max={120} step={5} value={scale} onChange={event => applyScale(Number(event.target.value))} />
      <p className="text-xs text-muted-foreground">Pulsa Guardar configuración para conservar esta escala en tu perfil, incluso al cerrar el navegador o entrar desde otro equipo.</p>
    </div>
    <div className="flex justify-end border-t pt-4"><ActionButton tone="edit" disabled={saving} onClick={async()=>{setSaving(true);try{await savePreferences();toast.success('Configuración personal guardada');}catch(error){toast.error(apiErrorMessage(error,'No se pudo guardar la configuración'));}finally{setSaving(false);}}}><Save className="size-4"/>{saving?'Guardando…':'Guardar configuración'}</ActionButton></div>
  </section>;
}
