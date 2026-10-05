import { useEffect, useRef, useState } from "react";
import { Camera, KeyRound, Save, Trash2, UserRound } from "lucide-react";
import { toast } from "sonner";

import { ActionButton } from "@/components/action-button";
import { getAvatarColor } from "@/components/avatar-color";
import { SearchableSelect } from "@/components/searchable-select";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Sheet, SheetBody, SheetContent, SheetDescription, SheetFooter, SheetHeader, SheetSection, SheetSectionDescription, SheetSectionTitle, SheetTitle } from "@/components/ui/sheet";
import { useAuth } from "@/context/AuthContext";
import { useTheme, type Theme } from "@/context/theme-context";
import { wolverineAPI } from "@/features/wolverine/api";
import { apiErrorMessage } from "@/lib/api-error";
import { avatarUrl } from "@/lib/avatar";

function initials(name: string) {
  const words = name.trim().split(/\s+/).filter(Boolean);
  return words.length > 1 ? `${words[0][0]}${words[1][0]}`.toUpperCase() : words[0]?.slice(0, 2).toUpperCase() || "U";
}

export function MyAccountSheet({ open, onOpenChange }: { open: boolean; onOpenChange: (open: boolean) => void }) {
  const { user, impersonation, refreshSession } = useAuth();
  const { theme, applyTheme } = useTheme();
  const fileRef = useRef<HTMLInputElement>(null);
  const [saving, setSaving] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [profile, setProfile] = useState({ nombre: "", apellido: "", username: "", correo: "", telefono: "" });
  const [password, setPassword] = useState({ clave_actual: "", nueva_clave: "", confirmar_clave: "" });
  const locked = Boolean(impersonation?.active);
  const userName = user ? `${user.nombre} ${user.apellido}`.trim() : "Usuario";

  useEffect(() => {
    if (user) setProfile({ nombre: user.nombre, apellido: user.apellido, username: user.username, correo: user.correo, telefono: user.telefono ?? "" });
  }, [user]);

  if (!user) return null;

  const saveProfile = async () => {
    setSaving(true);
    try {
      await wolverineAPI.updateMyAccount({ ...profile, telefono: profile.telefono.trim() || null });
      await refreshSession();
      toast.success("Tu cuenta fue actualizada");
    } catch (error) { toast.error(apiErrorMessage(error, "No se pudo actualizar tu cuenta")); }
    finally { setSaving(false); }
  };

  const uploadAvatar = async (file: File | undefined) => {
    if (!file) return;
    setUploading(true);
    try {
      await wolverineAPI.uploadMyAvatar(file);
      await refreshSession();
      toast.success("Avatar actualizado");
    } catch (error) { toast.error(apiErrorMessage(error, "No se pudo actualizar el avatar")); }
    finally { setUploading(false); if (fileRef.current) fileRef.current.value = ""; }
  };

  const removeAvatar = async () => {
    setUploading(true);
    try {
      await wolverineAPI.deleteMyAvatar();
      await refreshSession();
      toast.success("Avatar retirado");
    } catch (error) { toast.error(apiErrorMessage(error, "No se pudo retirar el avatar")); }
    finally { setUploading(false); }
  };

  const savePassword = async () => {
    setSaving(true);
    try {
      const result = await wolverineAPI.updateMyPassword(password);
      setPassword({ clave_actual: "", nueva_clave: "", confirmar_clave: "" });
      toast.success(result.message);
    } catch (error) { toast.error(apiErrorMessage(error, "No se pudo cambiar la contraseña")); }
    finally { setSaving(false); }
  };

  return <Sheet open={open} onOpenChange={onOpenChange}>
    <SheetContent className="w-full sm:max-w-xl">
      <SheetHeader><SheetTitle>Mi cuenta</SheetTitle><SheetDescription>Administra tu identidad, avatar, seguridad y preferencias personales.</SheetDescription></SheetHeader>
      <SheetBody className="space-y-7">
        {locked && <div className="rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900 dark:border-amber-900 dark:bg-amber-950/40 dark:text-amber-100">Estás editando los datos de {userName}. Los cambios quedarán registrados con tu identidad. Para cambiar contraseña, vuelve a tu cuenta.</div>}
        <SheetSection>
          <div><SheetSectionTitle>Avatar</SheetSectionTitle><SheetSectionDescription>PNG, JPG o WebP de hasta 20 MB. La foto se optimiza al guardar.</SheetSectionDescription></div>
          <div className="flex items-center gap-4">
            <Avatar className="size-20 ring-1 ring-border"><AvatarImage src={avatarUrl(user.avatar_file)} alt={userName} className="object-cover" /><AvatarFallback className={`${getAvatarColor(userName)} text-xl font-medium text-white`}>{initials(userName)}</AvatarFallback></Avatar>
            <div className="flex flex-wrap gap-2">
              <input ref={fileRef} className="hidden" type="file" accept="image/png,image/jpeg,image/webp" onChange={(event) => void uploadAvatar(event.target.files?.[0])} />
              <Button type="button" variant="outline" disabled={uploading} onClick={() => fileRef.current?.click()}><Camera className="size-4" />{uploading ? "Procesando..." : "Cambiar avatar"}</Button>
              {user.avatar_file && <Button type="button" variant="ghost" disabled={uploading} onClick={() => void removeAvatar()} className="text-destructive hover:text-destructive"><Trash2 className="size-4" />Retirar</Button>}
            </div>
          </div>
        </SheetSection>
        <SheetSection>
          <div><SheetSectionTitle>Datos personales</SheetSectionTitle><SheetSectionDescription>Estos datos identifican tu cuenta dentro de ABISSOL.</SheetSectionDescription></div>
          <div className="grid gap-5 sm:grid-cols-2">
            <div className="space-y-2"><Label htmlFor="account-name">Nombres</Label><Input id="account-name" value={profile.nombre} onChange={(event) => setProfile({ ...profile, nombre: event.target.value })} /></div>
            <div className="space-y-2"><Label htmlFor="account-lastname">Apellidos</Label><Input id="account-lastname" value={profile.apellido} onChange={(event) => setProfile({ ...profile, apellido: event.target.value })} /></div>
            <div className="space-y-2"><Label htmlFor="account-username">Usuario</Label><Input id="account-username" value={profile.username} onChange={(event) => setProfile({ ...profile, username: event.target.value })} /></div>
            <div className="space-y-2"><Label htmlFor="account-phone">Teléfono</Label><Input id="account-phone" inputMode="numeric" value={profile.telefono} onChange={(event) => setProfile({ ...profile, telefono: event.target.value.replace(/\D/g, "").slice(0, 9) })} /></div>
            <div className="space-y-2 sm:col-span-2"><Label htmlFor="account-email">Correo</Label><Input id="account-email" type="email" value={profile.correo} onChange={(event) => setProfile({ ...profile, correo: event.target.value })} /></div>
          </div>
          <ActionButton tone="edit" disabled={saving} onClick={() => void saveProfile()}><Save className="size-4" />{saving ? "Guardando..." : "Guardar datos"}</ActionButton>
        </SheetSection>
        <SheetSection>
          <div><SheetSectionTitle>Seguridad</SheetSectionTitle><SheetSectionDescription>Al cambiarla se cerrarán las demás sesiones, pero esta seguirá activa.</SheetSectionDescription></div>
          <div className="space-y-5">
            <div className="space-y-2"><Label htmlFor="account-current-password">Contraseña actual</Label><Input id="account-current-password" disabled={locked} type="password" autoComplete="current-password" value={password.clave_actual} onChange={(event) => setPassword({ ...password, clave_actual: event.target.value })} /></div>
            <div className="grid gap-5 sm:grid-cols-2"><div className="space-y-2"><Label htmlFor="account-new-password">Nueva contraseña</Label><Input id="account-new-password" disabled={locked} type="password" autoComplete="new-password" value={password.nueva_clave} onChange={(event) => setPassword({ ...password, nueva_clave: event.target.value })} /></div><div className="space-y-2"><Label htmlFor="account-confirm-password">Confirmar contraseña</Label><Input id="account-confirm-password" disabled={locked} type="password" autoComplete="new-password" value={password.confirmar_clave} onChange={(event) => setPassword({ ...password, confirmar_clave: event.target.value })} /></div></div>
          </div>
          <ActionButton tone="edit" disabled={locked || saving || !password.clave_actual || !password.nueva_clave || !password.confirmar_clave} onClick={() => void savePassword()}><KeyRound className="size-4" />Cambiar contraseña</ActionButton>
        </SheetSection>
        <SheetSection>
          <div><SheetSectionTitle>Preferencias</SheetSectionTitle><SheetSectionDescription>La apariencia se guarda en tu perfil.</SheetSectionDescription></div>
          <div className="space-y-2"><Label htmlFor="account-theme">Tema</Label><SearchableSelect id="account-theme" value={theme} onValueChange={(value) => applyTheme(value as Theme)} options={[{ value: "light", label: "Light" }, { value: "medium", label: "Medium" }, { value: "dark", label: "Dark" }, { value: "virtualia", label: "Virtual IA" }, { value: "lady", label: "Lady" }]} searchPlaceholder="Buscar tema..." /></div>
        </SheetSection>
      </SheetBody>
      <SheetFooter><Button type="button" variant="outline" onClick={() => onOpenChange(false)}><UserRound className="size-4" />Cerrar</Button></SheetFooter>
    </SheetContent>
  </Sheet>;
}
