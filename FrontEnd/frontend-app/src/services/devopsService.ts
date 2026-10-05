import api from "@/lib/api";

export type DevopsState =
  | "synced"
  | "dirty"
  | "ahead"
  | "behind"
  | "diverged"
  | "offline";

export interface DevopsStatus {
  repository: string;
  remote: string;
  remote_url: string;
  branch: string;
  protected_branch: string;
  is_protected_branch: boolean;
  developer_slug: string | null;
  developer_configured: boolean;
  personal_branch: string | null;
  is_personal_branch: boolean;
  upstream: string | null;
  branch_remote_ref: string;
  remote_branch_exists: boolean;
  publish_branch: string;
  local_commit: string;
  remote_commit: string | null;
  base_remote_commit: string | null;
  ahead: number;
  behind: number;
  upload_ahead: number;
  base_ahead: number;
  base_behind: number;
  main_contains_head: boolean;
  changes: string[];
  remote_changes: string[];
  ahead_changes: string[];
  upload_changes: string[];
  ahead_commits: string[];
  integration_pending: boolean;
  integration_busy: boolean;
  integration_busy_branch: string | null;
  integration_run_number: number | null;
  integration_run_url: string | null;
  integration_lock_error: string | null;
  state: DevopsState;
  message: string;
  fetch_error: string | null;
  pull_request_url: string | null;
  local_main_guard: boolean;
  local_branches: string[];
  remote_branches: string[];
  can_switch_branch: boolean;
  can_create_branch: boolean;
  can_pull: boolean;
  can_push: boolean;
  can_publish: boolean;
}

export interface DevopsResponse {
  message?: string;
  status: DevopsStatus;
  terminal: string[];
}

export interface DevopsIntegrationActivity {
  busy: boolean;
  branch: string | null;
  run_number: number | null;
  url: string | null;
  status: string | null;
  error: string | null;
}

export interface DevopsProgress {
  action: "status" | "branch" | "pull" | "push" | "publish" | null;
  state: "idle" | "running" | "success" | "failed" | "cancelled";
  terminal: string[];
  started_at: string | null;
  updated_at: string | null;
  finished_at: string | null;
  cancel_requested: boolean;
}

export type PublishTarget = "backend" | "frontend" | "both";

export interface DevopsLog {
  id: number;
  usuario_id: number | null;
  accion: string;
  estado: string;
  mensaje: string;
  commit_hash: string | null;
  salida: string | null;
  creado_en: string | null;
  origen: string | null;
  actor: string | null;
  creado_en_cliente: string | null;
}

export interface DevopsLogPage {
  items: DevopsLog[];
  total: number;
  counts: { all: number; success: number; failed: number; cancelled: number; publish: number };
}

export interface MaintenanceStatus {
  runtime: { python: string; executable: string };
  packages: Record<string, string | null>;
  database_migration: string | null;
  schema_managed: boolean;
  update_source: string;
  direct_install_allowed: boolean;
  publish_mode: string;
  workflow_configured: boolean;
}

export const devopsAPI = {
  getMaintenance: async (): Promise<MaintenanceStatus> => {
    const response = await api.get("/devops/maintenance");
    return response.data;
  },
  getProgress: async (): Promise<DevopsProgress> => {
    const response = await api.get("/devops/progress");
    return response.data;
  },

  getStatus: async (refresh = true): Promise<DevopsResponse> => {
    const response = await api.get("/devops/status", {
      params: { refresh },
      timeout: 5 * 60_000,
    });
    return response.data;
  },

  getIntegrationActivity: async (): Promise<DevopsIntegrationActivity> => {
    const response = await api.get("/devops/integration-activity", { timeout: 20_000 });
    return response.data;
  },

  getLogs: async (params: { page: number; page_size: 10 | 25 | 50 | "all"; search: string; filter_by: string; direction: "asc" | "desc" }): Promise<DevopsLogPage> => {
    const response = await api.get("/devops/logs", { params });
    return response.data;
  },
  cancelProgress: async (): Promise<DevopsProgress> => {
    const response = await api.post("/devops/progress/cancel");
    return response.data;
  },

  pull: async (): Promise<DevopsResponse> => {
    const response = await api.post("/devops/pull", undefined, { timeout: 15 * 60_000 });
    return response.data;
  },

  push: async (commitMessage: string): Promise<DevopsResponse> => {
    const response = await api.post(
      "/devops/push",
      { commit_message: commitMessage },
      { timeout: 15 * 60_000 },
    );
    return response.data;
  },

  changeBranch: async (branch: string, create: boolean): Promise<DevopsResponse> => {
    const response = await api.post(
      "/devops/branch",
      { branch, create },
      { timeout: 5 * 60_000 },
    );
    return response.data;
  },

  publish: async (target: PublishTarget): Promise<DevopsResponse> => {
    const response = await api.post("/devops/publish", { target }, { timeout: 15 * 60_000 });
    return response.data;
  },
};
