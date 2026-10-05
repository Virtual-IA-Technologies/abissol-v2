import { useEffect, useMemo, useState } from "react";
import { Bell, CheckCheck, Settings2 } from "lucide-react";
import { toast } from "sonner";

import { ActionButton } from "@/components/action-button";
import { Card, CardContent } from "@/components/ui/card";
import { Switch } from "@/components/ui/switch";
import { useAuth } from "@/context/AuthContext";
import { notificationsAPI } from "@/features/notifications/api";
import { useNotifications } from "@/features/notifications/notification-context";
import type { NotificationType } from "@/features/notifications/types";
import { NotificationInbox } from "@/features/notifications/inbox";
import { NotificationRulesPanel } from "@/features/notifications/rules-panel";

type View = "inbox" | "settings";

function TabButton({ active, children, onClick }: { active: boolean; children: string; onClick: () => void }) {
  return <button type="button" role="tab" aria-selected={active} onClick={onClick} className={`-mb-px flex shrink-0 items-center justify-center border-b-2 px-4 py-3 text-sm font-medium transition-colors ${active ? "border-sky-500 text-foreground" : "border-transparent text-muted-foreground hover:border-border hover:text-foreground"}`}>{children}</button>;
}

export default function NotificationsPage() {
  const { user } = useAuth();
  const { unread, markAllRead } = useNotifications();
  const [view, setView] = useState<View>("inbox");
  const [types, setTypes] = useState<NotificationType[]>([]);
  const [saving, setSaving] = useState(false);
  const programmer = user?.role_assignments.some((assignment) => {
    if (!assignment.is_active || !assignment.rol.es_superusuario) return false;
    if (assignment.is_permanent) return true;
    const now = Date.now();
    return Boolean(assignment.starts_at && assignment.ends_at && Date.parse(assignment.starts_at) <= now && now < Date.parse(assignment.ends_at));
  }) ?? false;

  useEffect(() => {
    if (view === "settings" && !types.length) void notificationsAPI.types().then(setTypes).catch(() => toast.error("No se pudo cargar la configuración"));
  }, [view, types.length]);

  const groups = useMemo(() => Object.entries(types.reduce<Record<string, NotificationType[]>>((result, item) => {
    (result[item.source] ||= []).push(item);
    return result;
  }, {})), [types]);

  const save = async () => {
    setSaving(true);
    try {
      await notificationsAPI.savePreferences(types.filter((item) => item.enabled).map((item) => item.event_type));
      toast.success("Preferencias actualizadas");
    } catch {
      toast.error("No se pudieron guardar las preferencias");
    } finally {
      setSaving(false);
    }
  };

  return <main className="space-y-4 p-4 md:p-6">
    <div className="flex flex-wrap items-start justify-between gap-3"><div><h1 className="flex items-center gap-2 text-2xl font-semibold"><Bell className="text-sky-600" />Notificaciones</h1><p className="text-sm text-muted-foreground">Buzón personal de avisos importantes de ABISSOL.</p></div>{view === "inbox" && unread > 0 && <ActionButton tone="edit" onClick={() => void markAllRead().catch(() => toast.error("No se pudieron marcar las notificaciones"))}><CheckCheck />Marcar todas como leídas</ActionButton>}{view === "settings" && <ActionButton tone="edit" disabled={saving} onClick={() => void save()}><Settings2 />{saving ? "Guardando..." : "Guardar preferencias"}</ActionButton>}</div>
    <div role="tablist" aria-label="Secciones de notificaciones" className="flex overflow-x-auto border-b"><TabButton active={view === "inbox"} onClick={() => setView("inbox")}>Notificaciones</TabButton>{programmer && <TabButton active={view === "settings"} onClick={() => setView("settings")}>Configuración</TabButton>}</div>
    {view === "inbox" ? <NotificationInbox /> : <div className="space-y-4"><NotificationRulesPanel types={types}/>{groups.map(([source, sourceTypes]) => <Card key={source} className="gap-0 py-0"><div className="border-b px-5 py-4 font-semibold">{source}</div><CardContent className="divide-y p-0">{sourceTypes.map((item) => <label key={item.event_type} className="flex cursor-pointer items-center justify-between gap-4 px-5 py-4"><span><strong className="block text-sm">{item.label}</strong><span className="text-xs text-muted-foreground">Aviso interno · {item.severity}</span></span><Switch checked={item.enabled} onCheckedChange={(enabled) => setTypes((current) => current.map((row) => row.event_type === item.event_type ? { ...row, enabled } : row))} aria-label={`Recibir ${item.label}`} /></label>)}</CardContent></Card>)}</div>}
  </main>;
}
