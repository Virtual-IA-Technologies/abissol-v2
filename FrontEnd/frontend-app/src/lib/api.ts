import axios, { type InternalAxiosRequestConfig } from "axios";

import type { WolverineSession } from "@/features/wolverine/types";

const apiOrigin = import.meta.env.VITE_API_URL || (import.meta.env.PROD ? window.location.origin : "http://localhost:8015");
export const API_ROOT = `${apiOrigin.replace(/\/$/, "")}/abissol/api/v1`;

type RetryableRequest = InternalAxiosRequestConfig & { _wolverineRetry?: boolean };
type UploadRequest = RetryableRequest & { _uploadId?: string };

function uploadEvent(config: UploadRequest | undefined, state: string, loaded = 0, total?: number) {
  if (config?._uploadId) window.dispatchEvent(new CustomEvent('abissol:upload', { detail: { id: config._uploadId, state, loaded, total } }));
}
let accessToken: string | null = null;
let refreshRequest: Promise<WolverineSession> | null = null;

export const sessionClient = axios.create({
  baseURL: API_ROOT,
  withCredentials: true,
  timeout: 30_000,
});

export function setAccessToken(token: string | null) {
  accessToken = token;
}

export function refreshDeviceSession(): Promise<WolverineSession> {
  if (!refreshRequest) {
    const refresh = () => sessionClient
      .post<WolverineSession>("/refresh-session")
      .then(({ data }) => {
        setAccessToken(data.access_token);
        return data;
      });
    // La cookie se comparte entre pestañas: cada renovación debe recibir la
    // credencial rotada por la anterior antes de enviar su solicitud.
    refreshRequest = (navigator.locks
      ? navigator.locks.request("abissol-wolverine-refresh", refresh)
      : refresh())
      .finally(() => {
        refreshRequest = null;
      });
  }
  return refreshRequest;
}

const api = axios.create({
  baseURL: API_ROOT,
  withCredentials: true,
  timeout: 30_000,
});

api.interceptors.request.use((config) => {
  const upload = config as UploadRequest;
  if (config.data instanceof FormData) {
    if (!upload._uploadId) {
      upload._uploadId = crypto.randomUUID();
      const original = config.onUploadProgress;
      config.onUploadProgress = event => {
        original?.(event);
        uploadEvent(upload, event.total && event.loaded >= event.total ? 'processing' : 'uploading', event.loaded, event.total);
      };
    }
    config.timeout = 30 * 60_000;
    uploadEvent(upload, 'uploading');
  }
  if (accessToken) config.headers.Authorization = `Bearer ${accessToken}`;
  config.headers["X-Requested-With"] = "XMLHttpRequest";
  return config;
});

api.interceptors.response.use(
  (response) => { uploadEvent(response.config, 'finished'); return response; },
  async (error) => {
    const request = error.config as RetryableRequest | undefined;
    const url = request?.url || "";
    const mayRefresh = error.response?.status === 401
      && request
      && !request._wolverineRetry
      && !url.includes("/login")
      && !url.includes("/refresh-session")
      && !url.includes("/logout-session");

    if (mayRefresh) {
      request._wolverineRetry = true;
      try {
        const session = await refreshDeviceSession();
        window.dispatchEvent(new CustomEvent("wolverine:session", { detail: session }));
        request.headers.Authorization = `Bearer ${session.access_token}`;
        return api(request);
      } catch {
        // El evento central limpia el estado y redirige una sola vez.
      }
    }
    if (error.response?.status === 401) {
      setAccessToken(null);
      window.dispatchEvent(new Event("wolverine:expired"));
    }
    uploadEvent(request, 'finished');
    return Promise.reject(error);
  },
);

export default api;
