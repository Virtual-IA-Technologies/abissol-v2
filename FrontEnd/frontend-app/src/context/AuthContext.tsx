import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";

import { refreshDeviceSession, setAccessToken } from "@/lib/api";
import { wolverineAPI } from "@/features/wolverine/api";
import type { AccessLevel, MenuNode, User, WolverineSession } from "@/features/wolverine/types";

const rank: Record<AccessLevel, number> = { none: 0, lector: 1, editor: 2, gestor: 3 };

interface AuthContextValue {
  user: User | null;
  token: string | null;
  loading: boolean;
  menus: MenuNode[];
  access: Record<string, AccessLevel>;
  impersonation: WolverineSession["impersonation"] | null;
  login: (session: WolverineSession) => void;
  logout: () => Promise<void>;
  startImpersonation: (userId: number) => Promise<void>;
  leaveImpersonation: () => Promise<void>;
  refreshSession: () => Promise<void>;
  can: (menuSlug: string, minimum?: AccessLevel) => boolean;
}

const AuthContext = createContext<AuthContextValue | null>(null);

function tokenExpiration(token: string): number | null {
  try {
    const payload = JSON.parse(atob(token.split(".")[1])) as { exp?: number };
    return payload.exp ? payload.exp * 1000 : null;
  } catch {
    return null;
  }
}

function moduleEntry(documentNode: Document): string | null {
  const script = Array.from(documentNode.querySelectorAll<HTMLScriptElement>('script[type="module"][src]'))[0];
  return script ? new URL(script.src, window.location.origin).pathname : null;
}

async function reloadWhenPublishedVersionChanges() {
  const currentEntry = moduleEntry(document);
  if (!currentEntry) return;
  const response = await fetch(`/index.html?version-check=${Date.now()}`, {
    cache: "no-store",
    credentials: "same-origin",
    headers: { "Cache-Control": "no-cache" },
  });
  if (!response.ok) return;
  const publishedEntry = moduleEntry(new DOMParser().parseFromString(await response.text(), "text/html"));
  if (publishedEntry && publishedEntry !== currentEntry) window.location.reload();
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [session, setSession] = useState<WolverineSession | null>(null);
  const [loading, setLoading] = useState(true);

  const applySession = useCallback((next: WolverineSession | null) => {
    setAccessToken(next?.access_token ?? null);
    setSession(next);
  }, []);

  useEffect(() => {
    refreshDeviceSession().then(applySession).catch(() => applySession(null)).finally(() => setLoading(false));
  }, [applySession]);

  useEffect(() => {
    const check = () => { void reloadWhenPublishedVersionChanges().catch(() => undefined); };
    const onVisibility = () => { if (document.visibilityState === "visible") check(); };
    const timer = window.setInterval(check, 30_000);
    window.addEventListener("focus", check);
    document.addEventListener("visibilitychange", onVisibility);
    check();
    return () => {
      window.clearInterval(timer);
      window.removeEventListener("focus", check);
      document.removeEventListener("visibilitychange", onVisibility);
    };
  }, []);

  useEffect(() => {
    const update = (event: Event) => applySession((event as CustomEvent<WolverineSession>).detail);
    const expire = () => applySession(null);
    window.addEventListener("wolverine:session", update);
    window.addEventListener("wolverine:expired", expire);
    return () => {
      window.removeEventListener("wolverine:session", update);
      window.removeEventListener("wolverine:expired", expire);
    };
  }, [applySession]);

  useEffect(() => {
    if (!session?.access_token) return;
    const expiration = tokenExpiration(session.access_token);
    const delay = Math.max(1_000, (expiration ?? Date.now()) - Date.now() - 60_000);
    const timer = window.setTimeout(() => {
      refreshDeviceSession().then(applySession).catch(() => applySession(null));
    }, delay);
    return () => window.clearTimeout(timer);
  }, [session?.access_token, applySession]);

  const logout = useCallback(async () => {
    try {
      await wolverineAPI.logout();
    } finally {
      applySession(null);
    }
  }, [applySession]);

  const value = useMemo<AuthContextValue>(() => ({
    user: session?.usuario ?? null,
    token: session?.access_token ?? null,
    loading,
    menus: session?.menus ?? [],
    access: session?.access ?? {},
    impersonation: session?.impersonation ?? null,
    login: applySession,
    logout,
    startImpersonation: async (userId) => applySession(await wolverineAPI.startImpersonation(userId)),
    leaveImpersonation: async () => applySession(await wolverineAPI.leaveImpersonation()),
    refreshSession: async () => applySession(await wolverineAPI.me()),
    can: (slug, minimum = "lector") => rank[session?.access[slug] ?? "none"] >= rank[minimum],
  }), [session, loading, applySession, logout]);

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) throw new Error("useAuth debe usarse dentro de AuthProvider");
  return context;
}
