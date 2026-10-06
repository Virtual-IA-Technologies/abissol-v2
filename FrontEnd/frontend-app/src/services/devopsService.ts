import api from "@/lib/api";
export interface DevopsStatus {
  branch: string; local_commit: string; remote_commit: string | null;
  ahead: number; behind: number; changes: string[]; message: string;
  state: string; read_only: boolean; deployment_configured: boolean;
  can_pull: boolean; can_push: boolean; can_publish: boolean;
}
export interface DevopsResponse { status: DevopsStatus; terminal: string[]; message?: string }
export interface DevopsProgress { state: string; terminal: string[]; action: string | null }
export interface DevopsLog {
  id: number; accion: string; estado: string; mensaje: string;
  commit_hash: string | null; salida: string | null; creado_en: string | null;
}
export const devopsAPI = {
  getStatus: async (refresh = true): Promise<DevopsResponse> =>
    (await api.get("/devops/status", { params: { refresh }, timeout: 120_000 })).data,
  getProgress: async (): Promise<DevopsProgress> => (await api.get("/devops/progress")).data,
  action: async (action: "pull" | "push" | "publish", commitMessage: string): Promise<DevopsResponse> =>
    (await api.post(`/devops/${action}`, { commit_message: commitMessage, target: "both" }, { timeout: 20 * 60_000 })).data,
  getLogs: async (page: number, search: string): Promise<{ items: DevopsLog[]; total: number }> =>
    (await api.get("/devops/logs", { params: { page, page_size: 10, search } })).data,
};
