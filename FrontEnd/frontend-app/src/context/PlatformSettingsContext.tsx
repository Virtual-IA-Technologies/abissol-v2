import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";

import { settingsAPI } from "@/features/settings/api";
import type { PlatformSettings, PlatformSettingsWrite } from "@/features/settings/types";

const defaults: PlatformSettings = {
  id: 0,
  app_title: "ABISSOL",
  organization_name: "ABISSOL",
  footer_text: "ABISSOL",
  primary_color: "#2563eb",
  ui_scale: 100,
  logo_light_url: null,
  logo_dark_url: null,
  favicon_url: null,
};

type SettingsContextValue = {
  settings: PlatformSettings;
  loading: boolean;
  update: (payload: PlatformSettingsWrite) => Promise<void>;
  uploadBranding: (files: { logo_light?: File; logo_dark?: File; favicon?: File }) => Promise<void>;
};

const SettingsContext = createContext<SettingsContextValue | null>(null);

function applySettings(settings: PlatformSettings) {
  document.title = settings.app_title;
  for (const variable of ["--primary", "--ring", "--sidebar-primary"]) {
    document.documentElement.style.setProperty(variable, settings.primary_color);
  }
  document.documentElement.style.setProperty("--primary-foreground", "#ffffff");
  document.documentElement.style.setProperty("--sidebar-primary-foreground", "#ffffff");
  if (settings.favicon_url) {
    let link = document.querySelector<HTMLLinkElement>("link[rel='icon']");
    if (!link) {
      link = document.createElement("link");
      link.rel = "icon";
      document.head.appendChild(link);
    }
    link.href = settings.favicon_url;
  }
}

export function PlatformSettingsProvider({ children }: { children: ReactNode }) {
  const [settings, setSettings] = useState(defaults);
  const [loading, setLoading] = useState(true);
  const accept = useCallback((next: PlatformSettings) => {
    setSettings(next);
    applySettings(next);
  }, []);

  useEffect(() => {
    settingsAPI.get().then(accept).catch(() => applySettings(defaults)).finally(() => setLoading(false));
  }, [accept]);

  const value = useMemo<SettingsContextValue>(() => ({
    settings,
    loading,
    update: async (payload) => accept(await settingsAPI.update(payload)),
    uploadBranding: async (files) => accept(await settingsAPI.uploadBranding(files)),
  }), [settings, loading, accept]);

  return <SettingsContext.Provider value={value}>{children}</SettingsContext.Provider>;
}

export function usePlatformSettings() {
  const context = useContext(SettingsContext);
  if (!context) throw new Error("usePlatformSettings debe usarse dentro de PlatformSettingsProvider");
  return context;
}
