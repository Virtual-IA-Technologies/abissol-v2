import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";

export type DeliveryChannels = { email: boolean; whatsapp: boolean };

export function DeliveryChannelsField({ value, onChange, hasEmail, hasWhatsapp, disabled }: { value: DeliveryChannels; onChange: (value: DeliveryChannels) => void; hasEmail: boolean; hasWhatsapp: boolean; disabled?: boolean }) {
  return <fieldset className="space-y-3 rounded-lg border p-3">
    <legend className="px-1 text-sm font-medium">Enviar confirmación</legend>
    <div className="flex items-center justify-between gap-3"><div><Label htmlFor="delivery-email">Correo</Label><p className="text-xs text-muted-foreground">{hasEmail ? "Usará el correo registrado." : "Registra un correo válido para habilitarlo."}</p></div><Switch id="delivery-email" checked={value.email} disabled={disabled || !hasEmail} onCheckedChange={(email) => onChange({ ...value, email })} /></div>
    <div className="flex items-center justify-between gap-3"><div><Label htmlFor="delivery-whatsapp">WhatsApp</Label><p className="text-xs text-muted-foreground">{hasWhatsapp ? "Usará el celular registrado." : "Registra un celular válido para habilitarlo."}</p></div><Switch id="delivery-whatsapp" checked={value.whatsapp} disabled={disabled || !hasWhatsapp} onCheckedChange={(whatsapp) => onChange({ ...value, whatsapp })} /></div>
  </fieldset>;
}
