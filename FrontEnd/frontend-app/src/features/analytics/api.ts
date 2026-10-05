import api from "@/lib/api";
import type { AuditStatistics, DashboardMetrics } from "./types";

export const analyticsAPI = {
  dashboard: async (signal?:AbortSignal,refresh=false) => (await api.get<DashboardMetrics>("/panel-principal/metricas",{signal,params:{refresh}})).data,
  audit: async (days: number) => (await api.get<AuditStatistics>("/auditoria/estadisticas", { params: { days } })).data,
};
