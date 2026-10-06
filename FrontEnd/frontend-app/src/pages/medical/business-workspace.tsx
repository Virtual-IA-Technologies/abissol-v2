import { useState, type ReactNode } from "react";
import { useSearchParams } from "react-router-dom";
import { FileText, Send, Mail, Users, HeartPulse, Settings2, Wallet, CalendarDays, History, Building2 } from "lucide-react";
import { UnderlineTabs } from "@/components/underline-tabs";
import { useAuth } from "@/context/AuthContext";
import { EmissionSettings, MetaDispatches } from "./business-workspace-panels";

export type SectionProps = { section: string; embedded?: boolean; liquidationKind?: string; history?: boolean };

export function BusinessWorkspace({ section, renderSection }: { section: string; renderSection: (props: SectionProps) => ReactNode }) {
  const { can, user } = useAuth();
  const [params, setParams] = useSearchParams();
  const [fallback, setFallback] = useState("list");
  const programmer = user?.roles?.some(role => role.nombre.toLowerCase() === "programador");
  const global = programmer || user?.roles?.some(role => role.nombre === "Administrador");
  const icon = (Icon: typeof FileText) => <Icon className="size-4" />;
  const tabs = section === "emissions" ? [
    { value:"list", label:"Emisiones", icon:icon(FileText) },
    ...(can("medical-dispatches", "lector") ? [{ value:"dispatches", label:"Envíos", icon:icon(Send) }] : []),
    ...(global ? [{ value:"meta", label:"Envíos META", icon:icon(Mail) }] : []),
    ...(can("medical-network", "lector") ? [{ value:"network", label:"Vendedores", icon:icon(Users) }] : []),
    ...(can("medical-plans", "lector") ? [{ value:"plans", label:"Planes", icon:icon(HeartPulse) }] : []),
    ...(programmer ? [{ value:"settings", label:"Configuración", icon:icon(Settings2) }] : []),
  ] : [
    { value:"list", label:"Liquidaciones", icon:icon(Wallet) },
    ...(global ? [{ value:"meta", label:"Liquidaciones mensuales", icon:icon(CalendarDays) }, { value:"platform", label:"Liquidación plataforma", icon:icon(Building2) }] : []),
    { value:"history", label:"Historial", icon:icon(History) },
  ];
  const requested = params.get("tab") || fallback;
  const tab = tabs.some(t => t.value === requested) ? requested : "list";
  const change = (next: string) => { setFallback(next); setParams({ tab: next }); };
  return <main className="min-w-0 space-y-5 p-4 md:p-6">
    <div><p className="text-xs font-medium uppercase tracking-widest text-emerald-600">Negocio ABISSOL</p><h1 className="mt-1 text-2xl font-semibold">{section === "emissions" ? "Emisiones" : "Liquidaciones"}</h1></div>
    <UnderlineTabs label={section === "emissions" ? "Secciones de emisiones" : "Secciones de liquidaciones"} value={tab} onChange={change} tabs={tabs}>
      {section === "emissions" ? tab === "meta" ? <MetaDispatches /> : tab === "settings" ? <EmissionSettings /> : renderSection({ section: tab === "list" ? "emissions" : tab, embedded:true })
        : renderSection({ section:"liquidations", embedded:true, liquidationKind: tab === "history" ? undefined : tab === "list" ? "seller" : tab, history:tab === "history" })}
    </UnderlineTabs>
  </main>;
}
