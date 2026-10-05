import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { toast } from "sonner";

import { useAuth } from "@/context/AuthContext";
import { connectNotificationSocket, notificationsAPI } from "./api";
import type { NotificationItem } from "./types";

type NotificationContextValue = {
  items: NotificationItem[];
  unread: number;
  loading: boolean;
  refresh: (unreadOnly?: boolean) => Promise<void>;
  markRead: (id: number) => Promise<void>;
  markAllRead: () => Promise<void>;
};

const NotificationContext = createContext<NotificationContextValue | null>(null);

export function NotificationProvider({ children }: { children: ReactNode }) {
  const { token, can } = useAuth();
  const allowed = can("notificaciones");
  const [items, setItems] = useState<NotificationItem[]>([]);
  const [unread, setUnread] = useState(0);
  const [loading, setLoading] = useState(false);
  const pendingRefreshes = useRef(new Map<boolean, Promise<void>>());
  const knownIds = useRef(new Set<number>());
  const sessionToken = useRef(token);
  sessionToken.current = token;
  const viewUnreadOnly = useRef(false);

  const refresh = useCallback((unreadOnly = false): Promise<void> => {
    if (!token || !allowed) return Promise.resolve();
    viewUnreadOnly.current = unreadOnly;
    const pending = pendingRefreshes.current.get(unreadOnly);
    if (pending) return pending;
    setLoading(true);
    const request = notificationsAPI.list(unreadOnly).then((result) => {
      if (sessionToken.current !== token || viewUnreadOnly.current !== unreadOnly) return;
      knownIds.current = new Set(result.items.map(item=>item.id));
      setItems(result.items);
      setUnread(result.unread);
    }).finally(() => {
      if(pendingRefreshes.current.get(unreadOnly)===request) pendingRefreshes.current.delete(unreadOnly);
      if (pendingRefreshes.current.size === 0) setLoading(false);
    });
    pendingRefreshes.current.set(unreadOnly, request);
    return request;
  }, [token, allowed]);

  useEffect(() => {
    pendingRefreshes.current.clear();
    if (!token || !allowed) {
      pendingRefreshes.current.clear();
      knownIds.current.clear();
      setItems([]);
      setUnread(0);
      return;
    }
    void refresh().catch(() => undefined);
    let connected = false;
    return connectNotificationSocket(
      token,
      (item) => {
        if (sessionToken.current !== token) return;
        const isNew = !knownIds.current.has(item.id);
        knownIds.current.add(item.id);
        if (knownIds.current.size>1000) knownIds.current=new Set([...knownIds.current].slice(-1000));
        setItems(current=>[item,...current.filter(entry=>entry.id!==item.id)].filter(entry=>!viewUnreadOnly.current||!entry.read_at).slice(0,100));
        if (isNew&&!item.read_at) setUnread(current=>current+1);
        if (isNew) toast(item.title, { description: item.message });
        // Si llegó durante una consulta, reconciliar al terminar sin perder el aviso.
        const pending=pendingRefreshes.current.get(viewUnreadOnly.current);
        if(pending) void pending.then(()=>refresh(viewUnreadOnly.current)).catch(()=>undefined);
      },
      () => { if(connected) void refresh(viewUnreadOnly.current).catch(() => undefined); connected=true; },
    );
  }, [token, allowed, refresh]);

  const markRead = useCallback(async (id: number) => {
    const target = items.find((item) => item.id === id);
    await notificationsAPI.read(id);
    setItems((current) => current.map((item) => item.id === id ? { ...item, read_at: item.read_at || new Date().toISOString() } : item));
    if (target && !target.read_at) setUnread((current) => Math.max(0, current - 1));
  }, [items]);

  const markAllRead = useCallback(async () => {
    await notificationsAPI.readAll();
    const now = new Date().toISOString();
    setItems((current) => current.map((item) => ({ ...item, read_at: item.read_at || now })));
    setUnread(0);
  }, []);

  const value = useMemo(() => ({ items, unread, loading, refresh, markRead, markAllRead }), [items, unread, loading, refresh, markRead, markAllRead]);
  return <NotificationContext.Provider value={value}>{children}</NotificationContext.Provider>;
}

// eslint-disable-next-line react-refresh/only-export-components
export function useNotifications() {
  const context = useContext(NotificationContext);
  if (!context) throw new Error("useNotifications debe usarse dentro de NotificationProvider");
  return context;
}
