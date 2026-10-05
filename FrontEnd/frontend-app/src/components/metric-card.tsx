import { Activity, Bell, Boxes, CalendarDays, Clock3, ShieldCheck, TriangleAlert, Users } from "lucide-react";
import { Link } from "react-router-dom";
import { Card, CardContent } from "@/components/ui/card";
import type { MetricCardData } from "@/features/analytics/types";

const icons = { activity: Activity, alert: TriangleAlert, bell: Bell, boxes: Boxes, calendar: CalendarDays, clock: Clock3, shield: ShieldCheck, users: Users };
const tones = {
  amber: "bg-amber-50 text-amber-700 dark:bg-amber-950/40 dark:text-amber-300", blue: "bg-blue-50 text-blue-700 dark:bg-blue-950/40 dark:text-blue-300",
  cyan: "bg-cyan-50 text-cyan-700 dark:bg-cyan-950/40 dark:text-cyan-300", emerald: "bg-emerald-50 text-emerald-700 dark:bg-emerald-950/40 dark:text-emerald-300",
  indigo: "bg-indigo-50 text-indigo-700 dark:bg-indigo-950/40 dark:text-indigo-300", red: "bg-red-50 text-red-700 dark:bg-red-950/40 dark:text-red-300",
};

export function MetricCard({ metric }: { metric: MetricCardData }) {
  const units=['B','KB','MB','GB','TB'];
  const exponent=metric.value>0?Math.min(4,Math.floor(Math.log(metric.value)/Math.log(1024))):0;
  const display=metric.format==='bytes'?`${(metric.value/1024**exponent).toLocaleString('es-PE',{maximumFractionDigits:1})} ${units[exponent]}`:metric.format==='currency'?metric.value.toLocaleString('es-PE',{style:'currency',currency:'PEN',maximumFractionDigits:2}):metric.value.toLocaleString('es-PE');
  const Icon = icons[metric.icon] ?? Activity;
  return <Link to={metric.url} className="block rounded-xl focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"><Card className="h-full border-border/70 shadow-sm transition-colors hover:border-sky-300"><CardContent className="flex items-start gap-4 p-5"><div className={`rounded-2xl p-3 ${tones[metric.tone]}`}><Icon className="size-5" /></div><div className="min-w-0"><p className="text-sm text-muted-foreground">{metric.label}</p><p className="mt-1 text-3xl font-semibold tabular-nums">{display}</p><p className="mt-1 text-xs leading-5 text-muted-foreground">{metric.description}</p></div></CardContent></Card></Link>;
}
