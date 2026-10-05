import api, { API_ROOT } from "@/lib/api";
import type { NotificationItem, NotificationType } from "./types";
export type InboxFilters = { page: number; limit: number; search: string; source: string; severity: string; unread_only: boolean };
export type InboxResult = { items: NotificationItem[]; unread: number; total: number; sources: string[] };
export type RecipientRule = { kind: 'eligible'|'participants'|'administrators'|'roles'|'users'; ids: number[] };
export type NoticeRule = { recipients: RecipientRule; channels: ('platform'|'email'|'whatsapp')[] };
export type RuleConfiguration = { rules: Record<string,NoticeRule>; roles: {id:number;name:string}[]; users: {id:number;name:string}[]; external_channels_enabled: boolean };

export const notificationsAPI = {
  rules: async () => (await api.get<RuleConfiguration>('/notificaciones/reglas')).data,
  saveRules: async (rules: Record<string,NoticeRule>) => { await api.put('/notificaciones/reglas',{rules}); },
  inbox: async (params: InboxFilters, signal?: AbortSignal) => (await api.get<InboxResult>('/notificaciones', { params, signal })).data,
  remove: async (ids: number[]) => { await api.post('/notificaciones/eliminar', { ids }); },
  list: async (unreadOnly = false, limit = 100) => (await api.get<{ items: NotificationItem[]; unread: number }>("/notificaciones", { params: { unread_only: unreadOnly, limit } })).data,
  types: async () => (await api.get<NotificationType[]>("/notificaciones/tipos")).data,
  savePreferences: async (enabledTypes: string[]) => (await api.put("/notificaciones/preferencias", { enabled_types: enabledTypes })).data,
  read: async (id: number) => { await api.patch(`/notificaciones/${id}/leer`); },
  readAll: async () => { await api.post("/notificaciones/leer-todas"); },
};

export function connectNotificationSocket(
  token: string,
  onNotification: (item: NotificationItem) => void,
  onReady: () => void,
) {
  let stopped = false;
  let socket: WebSocket | null = null;
  let retry: number | undefined;
  const connect = () => {
    socket = new WebSocket(`${API_ROOT.replace(/^http/, "ws")}/notificaciones/ws`);
    socket.addEventListener("open", () => socket?.send(JSON.stringify({ token })));
    socket.addEventListener("message", (event) => {
      try {
        const payload = JSON.parse(event.data) as { type: string; notification?: NotificationItem };
        if (payload.type === "ready") onReady();
        if (payload.type === "notification" && payload.notification) onNotification(payload.notification);
      } catch {
        // Un mensaje malformado no debe interrumpir la reconexion del buzon.
      }
    });
    socket.addEventListener("close", () => { if (!stopped) retry = window.setTimeout(connect, 3000); });
  };
  connect();
  return () => { stopped = true; if (retry) window.clearTimeout(retry); socket?.close(); };
}
