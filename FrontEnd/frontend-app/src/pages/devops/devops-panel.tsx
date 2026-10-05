import { useCallback, useDeferredValue, useEffect, useRef, useState } from "react";
import axios from "axios";
import {
  CheckCircle2,
  CloudDownload,
  CloudUpload,
  FileCode2,
  GitBranch,
  History,
  Layers3,
  Loader2,
  Monitor,
  RefreshCw,
  Rocket,
  Server,
  Sparkles,
  Square,
  TerminalSquare,
  TriangleAlert,
  Wrench,
} from "lucide-react";
import { toast } from "sonner";
import { useLocation } from "react-router-dom";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { ExcelDownloadButton } from "@/components/excel-download-button";
import { ListPagination } from "@/components/list-pagination";
import { StandardListToolbar } from "@/components/standard-list-toolbar";
import { downloadExcelXlsx, type SortDirection } from "@/lib/table-tools";
import type { PageSize } from "@/lib/use-list-pagination";
import { useIncomingSearch } from "@/lib/use-incoming-search";
import { usePlatformSettings } from "@/context/PlatformSettingsContext";
import { formatLimaDateTime } from "@/lib/dates";
import {
  Sheet,
  SheetBody,
  SheetContent,
  SheetDescription,
  SheetFooter,
  SheetHeader,
  SheetSection,
  SheetSectionDescription,
  SheetSectionTitle,
  SheetTitle,
} from "@/components/ui/sheet";
import {
  devopsAPI,
  type DevopsLog,
  type DevopsProgress,
  type DevopsResponse,
  type DevopsState,
  type DevopsStatus,
  type MaintenanceStatus,
  type PublishTarget,
} from "@/services/devopsService";

type RunningAction = "status" | "branch" | "pull" | "push" | "publish" | null;
type ProgressState = "idle" | "running" | "success" | "failed" | "cancelled";
type DevopsTab = "status" | "maintenance" | "history";
type OperationResult = {
  kind: "success" | "error";
  title: string;
  message: string;
  confirmedFinished: boolean;
} | null;

type StoredIntegration = {
  branch: string;
  commit: string;
  startedAt: string;
};

const INTEGRATION_STORAGE_KEY = "abissol.devops.pending-integration";
const INTEGRATION_REVIEW_AFTER_MS = 10 * 60 * 1000;

const stateLabels: Record<DevopsState, string> = {
  synced: "Sincronizado",
  dirty: "Cambios locales",
  ahead: "Pendiente de subir",
  behind: "Pendiente de bajar",
  diverged: "Revisión manual",
  offline: "Sin conexión",
};

const stateClasses: Record<DevopsState, string> = {
  synced: "border-emerald-200 bg-emerald-50 text-emerald-700",
  dirty: "border-amber-200 bg-amber-50 text-amber-700",
  ahead: "border-sky-200 bg-sky-50 text-sky-700",
  behind: "border-orange-200 bg-orange-50 text-orange-700",
  diverged: "border-red-200 bg-red-50 text-red-700",
  offline: "border-slate-200 bg-slate-100 text-slate-700",
};

function errorDetails(error: unknown): { message: string; terminal: string[] } {
  if (!axios.isAxiosError(error)) {
    return { message: "Ocurrió un error inesperado", terminal: [] };
  }

  const detail = error.response?.data?.detail;
  if (typeof detail === "string") {
    return { message: detail, terminal: [] };
  }

  return {
    message: detail?.message ?? error.message ?? "No se pudo completar la operación",
    terminal: Array.isArray(detail?.terminal) ? detail.terminal : [],
  };
}

function shortCommit(value?: string | null) {
  return value ? value.slice(0, 8) : "—";
}

function elapsedLabel(from: string | null, until: number) {
  if (!from) return "0 s";
  const seconds = Math.max(0, Math.floor((until - Date.parse(from)) / 1000));
  const minutes = Math.floor(seconds / 60);
  const remainder = seconds % 60;
  return minutes ? `${minutes} min ${remainder.toString().padStart(2, "0")} s` : `${seconds} s`;
}

function integrationIsPending(status: DevopsStatus | null) {
  return Boolean(
    status?.is_personal_branch
    && status.remote_branch_exists
    && status.ahead === 0
    && status.base_ahead > 0
    && status.changes.length === 0,
  );
}

function readStoredIntegration(): StoredIntegration | null {
  try {
    const raw = localStorage.getItem(INTEGRATION_STORAGE_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as Partial<StoredIntegration>;
    if (!parsed.branch || !parsed.commit || !parsed.startedAt) return null;
    return parsed as StoredIntegration;
  } catch {
    return null;
  }
}

function writeStoredIntegration(value: StoredIntegration | null) {
  if (value) localStorage.setItem(INTEGRATION_STORAGE_KEY, JSON.stringify(value));
  else localStorage.removeItem(INTEGRATION_STORAGE_KEY);
}

function changeDetails(change: string) {
  const code = change.slice(0, 2).trim() || "M";
  const path = change.slice(2).trim();
  const labels: Record<string, string> = {
    M: "Modificado",
    A: "Agregado",
    D: "Eliminado",
    R: "Renombrado",
    "??": "Nuevo",
  };
  return { code, path, label: labels[code] ?? "Modificado" };
}

function suggestedCommitMessage(changes: string[]) {
  const paths = changes.map((change) => changeDetails(change).path.toLowerCase());
  if (paths.some((path) => path.endsWith("devops-panel.tsx"))) {
    return "Mejora la visualización del panel DevOps";
  }
  if (paths.length === 1) {
    const filename = paths[0].split(/[\\/]/).pop();
    return `Actualiza ${filename ?? "archivo del proyecto"}`;
  }
  if (paths.every((path) => path.startsWith("frontend/"))) {
    return `Actualiza interfaz del frontend (${paths.length} archivos)`;
  }
  if (paths.every((path) => path.startsWith("backend/"))) {
    return `Actualiza servicios del backend (${paths.length} archivos)`;
  }
  return `Actualiza ${paths.length} archivos del proyecto`;
}

export default function DevopsPanel() {
  const location = useLocation();
  const { settings } = usePlatformSettings();
  const [status, setStatus] = useState<DevopsStatus | null>(null);
  const [logs, setLogs] = useState<DevopsLog[]>([]);
  const [maintenance, setMaintenance] = useState<MaintenanceStatus | null>(null);
  const [terminal, setTerminal] = useState<string[]>([
    "DevOps de ABISSOL listo. Consulta GitHub para comenzar.",
  ]);
  const [commitMessage, setCommitMessage] = useState("");
  const [filesOpen, setFilesOpen] = useState(false);
  const [filesKind, setFilesKind] = useState<"local" | "remote" | "ahead">("local");
  const [running, setRunning] = useState<RunningAction>(null);
  const [publishOpen, setPublishOpen] = useState(false);
  const [publishTarget, setPublishTarget] = useState<PublishTarget>("both");
  const [operationResult, setOperationResult] = useState<OperationResult>(null);
  const [progressState, setProgressState] = useState<ProgressState>("idle");
  const [progressStartedAt, setProgressStartedAt] = useState<string | null>(null);
  const [progressUpdatedAt, setProgressUpdatedAt] = useState<string | null>(null);
  const [cancelRequested, setCancelRequested] = useState(false);
  const [cancelOpen, setCancelOpen] = useState(false);
  const [clock, setClock] = useState(Date.now());
  const [integrationStartedAt, setIntegrationStartedAt] = useState<string | null>(null);
  const [logSearch, setLogSearch] = useIncomingSearch();
  const [logFilter, setLogFilter] = useState("all");
  const [logDirection, setLogDirection] = useState<SortDirection>("desc");
  const [logTotal, setLogTotal] = useState(0);
  const [logCounts, setLogCounts] = useState({ all: 0, success: 0, failed: 0, cancelled: 0, publish: 0 });
  const [logPage, setLogPage] = useState(1);
  const [logPageSize, setLogPageSize] = useState<PageSize>(10);
  const deferredLogSearch = useDeferredValue(logSearch);
  const progressTimerRef = useRef<number | null>(null);
  const terminalRef = useRef<HTMLPreElement>(null);
  const historyOnly = import.meta.env.PROD;
  const [activeTab, setActiveTab] = useState<DevopsTab>(historyOnly || new URLSearchParams(window.location.search).get("seccion") === "historial" ? "history" : "status");

  useEffect(() => {
    if (new URLSearchParams(location.search).get("seccion") === "historial") setActiveTab("history");
  }, [location.search]);

  const visibleLogs = logs;
  const logTotalPages = logPageSize === "all" ? 1 : Math.max(1, Math.ceil(logTotal / logPageSize));
  const logParams = useCallback((pageSize: PageSize = logPageSize, page = logPage, search = deferredLogSearch) => ({ page, page_size: pageSize, search, filter_by: logFilter, direction: logDirection }), [logPageSize, logPage, deferredLogSearch, logFilter, logDirection]);
  const exportLogs = async () => {
    const result = await devopsAPI.getLogs(logParams("all", 1, logSearch));
    return downloadExcelXlsx("historial-devops", result.items, [
    { header: "Fecha", value: (log) => formatLimaDateTime(log.creado_en) },
    { header: "Accion", value: (log) => log.accion },
    { header: "Estado", value: (log) => log.estado },
    { header: "Mensaje", value: (log) => log.mensaje },
    { header: "Origen", value: (log) => log.origen },
    { header: "Actor", value: (log) => log.actor },
    { header: "Commit", value: (log) => log.commit_hash },
    ], { organizationName: settings.organization_name, criteria: { Busqueda: logSearch || "Sin busqueda", Estado_tipo: logFilter, Orden: `fecha-${logDirection}`, Registros: result.total } });
  };

  const stopProgressPolling = useCallback(() => {
    if (progressTimerRef.current !== null) {
      window.clearInterval(progressTimerRef.current);
      progressTimerRef.current = null;
    }
  }, []);

  const applyProgress = useCallback((progress: DevopsProgress) => {
    setProgressState(progress.state);
    setProgressStartedAt(progress.started_at);
    setProgressUpdatedAt(progress.updated_at);
    setCancelRequested(progress.cancel_requested);
    if (progress.terminal.length) setTerminal(progress.terminal);
    if (progress.state === "running" && progress.action) {
      setRunning(progress.action);
    }
  }, []);

  const startProgressPolling = useCallback((action: Exclude<RunningAction, null>) => {
    stopProgressPolling();
    let requestInProgress = false;
    const updateProgress = async () => {
      if (requestInProgress) return;
      requestInProgress = true;
      try {
        const progress = await devopsAPI.getProgress();
        if (progress.action === action) {
          applyProgress(progress);
          if (progress.state !== "running") {
            setRunning(null);
            stopProgressPolling();
          }
        }
      } catch {
        // La petición principal mostrará el error si se pierde la conexión.
      } finally {
        requestInProgress = false;
      }
    };
    void updateProgress();
    progressTimerRef.current = window.setInterval(updateProgress, 500);
  }, [applyProgress, stopProgressPolling]);

  const loadLogs = useCallback(async () => {
    try {
      const result = await devopsAPI.getLogs(logParams());
      setLogs(result.items);
      setLogTotal(result.total);
      setLogCounts(result.counts);
    } catch {
      setLogs([]);
    }
  }, [logParams]);

  const loadMaintenance = useCallback(async () => {
    try {
      setMaintenance(await devopsAPI.getMaintenance());
    } catch {
      setMaintenance(null);
    }
  }, []);

  const applyResponse = useCallback((response: DevopsResponse) => {
    setStatus(response.status);
    if (response.status.changes.length) {
      setCommitMessage((current) => current || suggestedCommitMessage(response.status.changes));
    }
    if (response.terminal.length) setTerminal(response.terminal);
    if (response.message) toast.success(response.message);
  }, []);

  const refreshStatus = useCallback(async () => {
    const startedAt = new Date().toISOString();
    setRunning("status");
    setProgressState("running");
    setProgressStartedAt(startedAt);
    setProgressUpdatedAt(startedAt);
    setCancelRequested(false);
    setTerminal(["$ git fetch origin --prune", "Consultando GitHub..."]);
    const request = devopsAPI.getStatus(true);
    startProgressPolling("status");
    try {
      applyResponse(await request);
      setProgressState("success");
    } catch (error) {
      const detail = errorDetails(error);
      setTerminal(detail.terminal.length ? detail.terminal : [detail.message]);
      setProgressState("failed");
      toast.error(detail.message);
      setOperationResult({
        kind: "error",
        title: "No se pudo completar la operación",
        message: detail.message,
        confirmedFinished: axios.isAxiosError(error) && Boolean(error.response),
      });
    } finally {
      stopProgressPolling();
      setRunning(null);
    }
  }, [applyResponse, startProgressPolling, stopProgressPolling]);

  useEffect(() => {
    if (historyOnly) return stopProgressPolling;
    let active = true;
    const initialize = async () => {
      try {
        const progress = await devopsAPI.getProgress();
        if (!active) return;
        applyProgress(progress);
        if (progress.state === "running" && progress.action) {
          startProgressPolling(progress.action);
        } else {
          void refreshStatus();
        }
      } catch {
        if (active) void refreshStatus();
      }
    };
    void initialize();
    return () => {
      active = false;
      stopProgressPolling();
    };
  }, [applyProgress, historyOnly, refreshStatus, startProgressPolling, stopProgressPolling]);

  useEffect(() => {
    if (activeTab === "maintenance" && !historyOnly) void loadMaintenance();
  }, [activeTab, historyOnly, loadMaintenance]);

  useEffect(() => {
    if (activeTab === "history") void loadLogs();
  }, [activeTab, loadLogs]);

  const busy = running !== null;
  const waitingForIntegration = Boolean(
    !historyOnly
    && !busy
    && integrationIsPending(status),
  );
  const waitingForTurn = Boolean(
    !historyOnly
    && !busy
    && status?.integration_busy
    && !waitingForIntegration,
  );

  useEffect(() => {
    if (progressState !== "running" && !waitingForIntegration) return;
    setClock(Date.now());
    const timer = window.setInterval(() => setClock(Date.now()), 1000);
    return () => window.clearInterval(timer);
  }, [progressState, waitingForIntegration]);

  useEffect(() => {
    if (!status?.is_personal_branch) return;
    const stored = readStoredIntegration();
    if (integrationIsPending(status)) {
      const pending = stored?.branch === status.branch && stored.commit === status.local_commit
        ? stored
        : {
            branch: status.branch,
            commit: status.local_commit,
            startedAt: new Date().toISOString(),
          };
      writeStoredIntegration(pending);
      setIntegrationStartedAt(pending.startedAt);
      return;
    }

    if (status.can_publish && stored?.branch === status.branch) {
      writeStoredIntegration(null);
      setIntegrationStartedAt(null);
      setTerminal((current) => [
        ...current,
        "✓ GitHub terminó las pruebas; la rama local se sincronizó automáticamente y Publicar ya está disponible.",
      ]);
      toast.success("Integración terminada. Ya puedes publicar.");
      setOperationResult({
        kind: "success",
        title: "Integración terminada",
        message: "GitHub aprobó los cambios, la copia local ya coincide con main y Publicar está disponible.",
        confirmedFinished: true,
      });
      return;
    }

    const stale = stored && (
      stored.branch !== status.branch
      || status.changes.length > 0
      || status.local_commit !== stored.commit
    );
    if (stale) writeStoredIntegration(null);
    setIntegrationStartedAt(null);
  }, [status]);

  useEffect(() => {
    if (!waitingForIntegration && !waitingForTurn) return;

    let polling = false;
    const checkIntegration = async () => {
      if (polling) return;
      polling = true;
      try {
        if (waitingForIntegration) {
          const response = await devopsAPI.getStatus(true);
          setStatus(response.status);
        } else {
          const activity = await devopsAPI.getIntegrationActivity();
          if (activity.busy) {
            setStatus((current) => current && ({
              ...current,
              integration_busy: true,
              integration_busy_branch: activity.branch,
              integration_run_number: activity.run_number,
              integration_run_url: activity.url,
              integration_lock_error: activity.error,
            }));
          } else {
            await refreshStatus();
          }
        }
      } catch {
        // Un fallo transitorio no altera el trabajo; el siguiente ciclo reintenta.
      } finally {
        polling = false;
      }
    };

    const timer = window.setInterval(() => {
      void checkIntegration();
    }, 4_000);
    void checkIntegration();
    return () => window.clearInterval(timer);
  }, [refreshStatus, waitingForIntegration, waitingForTurn]);

  useEffect(() => {
    if (terminalRef.current) {
      terminalRef.current.scrollTop = terminalRef.current.scrollHeight;
    }
  }, [terminal]);

  const runAction = async (
    action: Exclude<RunningAction, "status" | "branch" | null>,
    target: PublishTarget = "both",
  ) => {
    const startedAt = new Date().toISOString();
    setRunning(action);
    setProgressState("running");
    setProgressStartedAt(startedAt);
    setProgressUpdatedAt(startedAt);
    setCancelRequested(false);
    setTerminal([
      action === "pull"
        ? "Verificando que el proyecto estÃ© limpio antes de descargar..."
        : action === "push"
          ? `$ git add / commit / push origin ${status?.branch ?? "<rama>"}`
          : target === "backend"
            ? "$ preparar release backend → production"
            : target === "frontend"
              ? "$ npm run build && preparar release frontend → production"
              : "$ npm run build && preparar release completa → production",
      "Ejecutando operación segura...",
    ]);

    const request =
        action === "pull"
          ? devopsAPI.pull()
          : action === "push"
            ? devopsAPI.push(commitMessage)
            : devopsAPI.publish(target);
    startProgressPolling(action);

    try {
      const response = await request;
      applyResponse(response);
      setProgressState("success");
      const uploadedAndWaiting = action === "push" && integrationIsPending(response.status);
      if (uploadedAndWaiting) {
        setOperationResult(null);
      } else {
        setOperationResult({
          kind: "success",
          title: "Proceso completado",
          message: response.message ?? "La operación terminó correctamente.",
          confirmedFinished: true,
        });
      }
      if (action === "push") setCommitMessage("");
      if (activeTab === "history") await loadLogs();
    } catch (error) {
      const detail = errorDetails(error);
      const wasCancelled = detail.message.toLowerCase().includes("cancelad");
      setTerminal(detail.terminal.length ? detail.terminal : [detail.message]);
      setProgressState(wasCancelled ? "cancelled" : "failed");
      if (wasCancelled) toast.info("Proceso DevOps detenido.");
      else toast.error(detail.message);
      setOperationResult({
        kind: "error",
        title: "No se pudo completar la operación",
        message: detail.message,
        confirmedFinished: axios.isAxiosError(error) && Boolean(error.response),
      });
      if (activeTab === "history") await loadLogs();
    } finally {
      try { applyProgress(await devopsAPI.getProgress()); } catch { /* Keep the latest local state. */ }
      stopProgressPolling();
      setRunning(null);
    }
  };

  const runBranchAction = async (branch: string, create: boolean) => {
    const normalized = branch.trim();
    if (!normalized) return;
    const startedAt = new Date().toISOString();
    setRunning("branch");
    setProgressState("running");
    setProgressStartedAt(startedAt);
    setProgressUpdatedAt(startedAt);
    setTerminal([create ? `$ git switch -c ${normalized}` : `$ git switch ${normalized}`]);
    startProgressPolling("branch");
    try {
      const response = await devopsAPI.changeBranch(normalized, create);
      applyResponse(response);
      setProgressState("success");
      setOperationResult({
        kind: "success",
        title: create ? "Rama creada" : "Rama cambiada",
        message: response.message ?? "La rama activa fue actualizada.",
        confirmedFinished: true,
      });
    } catch (error) {
      const detail = errorDetails(error);
      setTerminal(detail.terminal.length ? detail.terminal : [detail.message]);
      setProgressState("failed");
      toast.error(detail.message);
      setOperationResult({
        kind: "error",
        title: "No se pudo cambiar la rama",
        message: detail.message,
        confirmedFinished: axios.isAxiosError(error) && Boolean(error.response),
      });
    } finally {
      stopProgressPolling();
      setRunning(null);
    }
  };

  const cancelProcess = async () => {
    setCancelOpen(false);
    setCancelRequested(true);
    try {
      applyProgress(await devopsAPI.cancelProgress());
      toast.info("Cancelacion solicitada. Esperando que el proceso se detenga...");
    } catch (error) {
      const detail = errorDetails(error);
      setCancelRequested(false);
      toast.error(detail.message);
    }
  };

  const totalElapsed = elapsedLabel(progressStartedAt, clock);
  const inactiveElapsed = elapsedLabel(progressUpdatedAt, clock);
  const integrationElapsed = elapsedLabel(integrationStartedAt, clock);
  const integrationNeedsReview = Boolean(
    waitingForIntegration
    && integrationStartedAt
    && clock - Date.parse(integrationStartedAt) >= INTEGRATION_REVIEW_AFTER_MS,
  );
  const displayedFiles = filesKind === "remote"
    ? (status?.remote_changes ?? [])
    : filesKind === "ahead"
      ? (status?.upload_changes ?? [])
      : (status?.changes ?? []);

  return (
    <main className="space-y-4 p-3 md:p-4">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <div className="flex items-center gap-2">
            <GitBranch className="h-6 w-6 text-emerald-600" />
            <h1 className="text-2xl font-semibold tracking-tight">DevOps</h1>
          </div>
          <p className="mt-1 text-sm text-muted-foreground">
            {historyOnly
              ? "Historial de las operaciones DevOps realizadas desde los equipos locales."
              : "Herramientas del repositorio ABISSOL V2. El despliegue todavía no está configurado."}
          </p>
        </div>
        {activeTab === "history" ? (
          <div className="flex flex-wrap items-center gap-2">
            <Button variant="outline" onClick={() => void loadLogs()}>
              <RefreshCw />
              Actualizar historial
            </Button>
            <ExcelDownloadButton onDownload={exportLogs} disabled={logTotal === 0} />
          </div>
        ) : activeTab === "maintenance" ? (
          <Button variant="outline" onClick={() => void loadMaintenance()}>
            <RefreshCw />
            Actualizar mantenimiento
          </Button>
        ) : (
          <Button variant="outline" onClick={() => void refreshStatus()} disabled={busy}>
            {running === "status" ? <Loader2 className="animate-spin" /> : <RefreshCw />}
            Consultar GitHub
          </Button>
        )}
      </div>

      {!historyOnly && (
        <div className="flex w-full overflow-x-auto border-b [scrollbar-width:none] [&::-webkit-scrollbar]:hidden" role="tablist" aria-label="Secciones DevOps">
          <DevopsTabButton active={activeTab === "status"} icon={<TerminalSquare />} onClick={() => setActiveTab("status")}>Estado</DevopsTabButton>
          <DevopsTabButton active={activeTab === "maintenance"} icon={<Wrench />} onClick={() => setActiveTab("maintenance")}>Centro de mantenimiento</DevopsTabButton>
          <DevopsTabButton active={activeTab === "history"} icon={<History />} onClick={() => setActiveTab("history")}>Historial y logs</DevopsTabButton>
        </div>
      )}

      {!historyOnly && activeTab === "status" && <>
      <Card className="gap-0 py-0">
        <CardHeader className="border-b px-5 py-3">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <CardTitle>Estado del repositorio</CardTitle>
              <CardDescription className="mt-1">
                {status?.remote_url ?? "Repositorio ABISSOL pendiente de configurar"}
              </CardDescription>
            </div>
            {status && (
              <Badge className={stateClasses[status.state]}>
                {status.state === "synced" && <CheckCircle2 />}
                {stateLabels[status.state]}
              </Badge>
            )}
          </div>
        </CardHeader>
        <CardContent className="px-5 py-3">
          <p className="mb-3 text-sm">{status?.message ?? "Consultando estado..."}</p>
          <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-4 xl:grid-cols-7">
            <StatusValue label="Rama local" value={status?.branch ?? "—"} />
            <StatusValue
              label="Commit local / GitHub"
              value={`${shortCommit(status?.local_commit)} / ${shortCommit(status?.remote_commit)}`}
              mono
            />
            <StatusValue
              label="Archivos locales"
              value={String(status?.changes.length ?? 0)}
              onClick={() => { setFilesKind("local"); setFilesOpen(true); }}
            />
            <StatusValue
              label="Por subir"
              value={`${status?.upload_ahead ?? 0} commit(s) / ${status?.upload_changes?.length ?? 0} archivo(s)`}
              onClick={() => { setFilesKind("ahead"); setFilesOpen(true); }}
            />
            <StatusValue label="Por bajar" value={`${status?.behind ?? 0} commit(s) / ${status?.remote_changes?.length ?? 0} archivo(s)`} onClick={() => { setFilesKind("remote"); setFilesOpen(true); }} />
            <StatusValue
              label="Respecto a main"
              value={`+${status?.base_ahead ?? 0} / -${status?.base_behind ?? 0}`}
            />
            <StatusValue
              label="Protección local de main"
              value={status?.local_main_guard ? "Activa" : "Inactiva"}
            />
          </div>
        </CardContent>
      </Card>

      {status && !status.is_personal_branch && <Card className="gap-3 py-4">
        <CardHeader className="px-4 py-0">
          <div className="flex items-center gap-2">
            <GitBranch className="h-5 w-5 text-emerald-600" />
            <CardTitle>Espacio de trabajo personal</CardTitle>
          </div>
          <CardDescription>
            Cada equipo usa una rama fija. Subir termina rápido; GitHub prueba en segundo plano y DevOps sincroniza esta copia automáticamente al integrar, sin publicar producción.
          </CardDescription>
        </CardHeader>
        <CardContent className="flex flex-wrap items-center justify-between gap-3 px-4 pb-0">
          <div>
            <p className="font-mono text-sm font-medium">{status?.personal_branch ?? "Sin configurar"}</p>
            <p className="mt-1 text-xs text-muted-foreground">
              {status.developer_configured
                ? "Activa esta rama antes de trabajar."
                : "Configura DEVOPS_DEVELOPER_SLUG en BackEnd/.env."}
            </p>
          </div>
          {status.personal_branch && (() => {
            const exists = status.local_branches.includes(status.personal_branch)
              || status.remote_branches.includes(status.personal_branch);
            return (
              <Button
                type="button"
                disabled={busy || (exists ? !status.can_switch_branch : !status.can_create_branch)}
                onClick={() => void runBranchAction(status.personal_branch!, !exists)}
              >
                {running === "branch" && <Loader2 className="animate-spin" />}
                {exists ? "Usar mi rama" : "Crear mi rama"}
              </Button>
            );
          })()}
        </CardContent>
      </Card>}

      <div className="grid gap-3 lg:grid-cols-3">
        <ActionCard
          icon={<CloudDownload className="h-5 w-5 text-sky-600" />}
          title="Bajar trabajo compartido"
          description="Actualiza tu rama personal cuando no tienes trabajo pendiente. Subir ya incorpora el main vigente en GitHub sin mezclarlo en esta carpeta."
          button="Bajar y sincronizar"
          loading={running === "pull"}
          disabled={busy || waitingForIntegration || !status?.can_pull}
          onClick={() => void runAction("pull")}
        />

        <Card className="gap-3 py-4">
          <CardHeader className="px-4 py-0">
            <div className="flex items-center gap-2">
              <CloudUpload className="h-5 w-5 text-emerald-600" />
              <CardTitle>Subir e integrar en GitHub</CardTitle>
            </div>
            <CardDescription>
              {status?.is_personal_branch
                ? `Guarda en ${status.branch}; GitHub toma un turno, incorpora el main vigente, prueba y sincroniza esta copia sin pedir Bajar.`
                : `Activa ${status?.personal_branch ?? "la rama personal configurada"} antes de subir.`}
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-2 px-4 pb-0">
            {status?.is_personal_branch && !waitingForIntegration && (
              <div className="flex gap-2">
                <Input
                  value={commitMessage}
                  onChange={(event) => setCommitMessage(event.target.value)}
                  placeholder="Descripción del cambio"
                  maxLength={180}
                />
                <Button
                  type="button"
                  variant="outline"
                  size="icon"
                  title="Sugerir descripción"
                  disabled={!status?.changes.length}
                  onClick={() => setCommitMessage(suggestedCommitMessage(status?.changes ?? []))}
                >
                  <Sparkles />
                  <span className="sr-only">Sugerir descripción</span>
                </Button>
              </div>
            )}
            {waitingForIntegration && (
              <div
                className={`flex items-center gap-3 rounded-lg border px-3 py-2 ${
                  integrationNeedsReview
                    ? "border-red-200 bg-red-50 text-red-900"
                    : "border-amber-200 bg-amber-50 text-amber-900"
                }`}
                role={integrationNeedsReview ? "alert" : "status"}
                aria-live="polite"
              >
                {integrationNeedsReview
                  ? <TriangleAlert className="h-5 w-5 shrink-0 text-red-600" />
                  : <Loader2 className="h-5 w-5 shrink-0 animate-spin text-amber-600" />}
                <div className="min-w-0">
                  <p className="text-sm font-semibold">
                    {integrationNeedsReview ? "Integración requiere revisión" : "Integrando en GitHub"} · {integrationElapsed}
                  </p>
                  <p className={`text-xs ${integrationNeedsReview ? "text-red-700" : "text-amber-700"}`}>
                    {integrationNeedsReview
                      ? "GitHub no confirmó la integración dentro del tiempo normal. Abre el detalle; Publicar seguirá bloqueado."
                      : "Pruebas en curso. Espera aquí; Publicar se habilitará automáticamente."}
                  </p>
                </div>
              </div>
            )}
            {waitingForTurn && (
              <div className="flex items-center gap-3 rounded-lg border border-sky-200 bg-sky-50 px-3 py-2 text-sky-900" role="status" aria-live="polite">
                <Loader2 className="h-5 w-5 shrink-0 animate-spin text-sky-600" />
                <div className="min-w-0 flex-1">
                  <p className="text-sm font-semibold">Turno ocupado por {status?.integration_busy_branch ?? "otra entrega"}</p>
                  <p className="text-xs text-sky-700">Subir se habilitará automáticamente al terminar. No necesitas bajar sus cambios.</p>
                </div>
                {status?.integration_run_url && <Button asChild size="sm" variant="outline"><a href={status.integration_run_url} target="_blank" rel="noreferrer">Ver turno</a></Button>}
              </div>
            )}
            <Button
              className="w-full"
              disabled={busy || !status?.can_push || (!!status?.changes.length && !commitMessage.trim())}
              onClick={() => void runAction("push")}
            >
              {running === "push" && <Loader2 className="animate-spin" />}
              Subir, probar e integrar
            </Button>
            {status?.pull_request_url && status.base_ahead > 0 && status.remote_branch_exists && (
              <Button asChild type="button" variant="outline" className="w-full">
                <a href={status.pull_request_url} target="_blank" rel="noreferrer">
                  Ver integración hacia {status.protected_branch}
                </a>
              </Button>
            )}
          </CardContent>
        </Card>

        <ActionCard
          icon={<Rocket className="h-5 w-5 text-violet-600" />}
          title="Preparar publicación"
          description="Disponible únicamente cuando la rama personal está limpia y coincide exactamente con main integrado."
          button="Abrir publicación"
          loading={running === "publish"}
          disabled={busy || !status?.can_publish}
          onClick={() => setPublishOpen(true)}
        />
      </div>

      <Card className="gap-0 overflow-hidden border-slate-800 bg-slate-950 py-0 text-slate-100">
        <CardHeader className="border-b border-slate-800 px-5 py-3">
          <div className="flex flex-wrap items-center gap-3">
            <div className="flex items-center gap-2">
              <TerminalSquare className="h-5 w-5 text-emerald-400" />
              <CardTitle>Terminal en tiempo real</CardTitle>
            </div>
            <div className="ml-auto flex flex-wrap items-center justify-end gap-x-4 gap-y-2 text-xs text-slate-400">
              {waitingForIntegration && <span>Integración: <strong className="text-amber-300">{integrationElapsed}</strong></span>}
              {progressState === "running" && <span>Total: <strong className="text-slate-200">{totalElapsed}</strong></span>}
              {progressState === "running" && <span>Última salida: <strong className={clock - Date.parse(progressUpdatedAt ?? "") > 15000 ? "text-amber-300" : "text-emerald-300"}>{inactiveElapsed}</strong></span>}
              <span className={`flex items-center gap-1.5 ${progressState === "failed" || progressState === "cancelled" ? "text-red-400" : ""}`}>
                {(progressState === "running" || (waitingForIntegration && !integrationNeedsReview)) && <Loader2 className="h-4 w-4 animate-spin text-emerald-400" />}
                {integrationNeedsReview && <TriangleAlert className="h-4 w-4 text-red-400" />}
                {cancelRequested
                  ? "Deteniendo…"
                  : integrationNeedsReview
                    ? "Revisar integración"
                    : waitingForIntegration
                    ? "Integrando en GitHub"
                    : progressState === "running"
                      ? "Trabajando"
                      : progressState === "success"
                        ? "Completado"
                        : progressState === "failed"
                          ? "Falló"
                          : progressState === "cancelled"
                            ? "Detenido"
                            : "En espera"}
              </span>
              {progressState === "running" && (
                <Button type="button" variant="destructive" size="sm" disabled={cancelRequested} onClick={() => setCancelOpen(true)}>
                  <Square className="fill-current" />
                  Detener
                </Button>
              )}
            </div>
          </div>
        </CardHeader>
        <CardContent className="p-0">
          <pre ref={terminalRef} className="max-h-[360px] min-h-44 overflow-auto whitespace-pre-wrap p-4 font-mono text-xs leading-5 text-slate-300">
            {terminal.join("\n\n")}
          </pre>
        </CardContent>
      </Card>
      </>}

      {!historyOnly && activeTab === "maintenance" && (
        <Card className="gap-0 py-0">
          <CardHeader className="border-b px-5 py-3">
            <div className="flex items-center gap-2">
              <Wrench className="h-5 w-5 text-blue-600" />
              <CardTitle>Centro de mantenimiento</CardTitle>
              <Badge className="ml-auto border-emerald-200 bg-emerald-50 text-emerald-700">
                Actualización protegida
              </Badge>
            </div>
            <CardDescription>
              Dependabot propone cambios; GitHub Actions valida antes de permitir producción.
            </CardDescription>
          </CardHeader>
          <CardContent className="grid gap-3 px-5 py-4 sm:grid-cols-2 lg:grid-cols-4">
            <StatusValue label="Python" value={maintenance?.runtime.python ?? "Consultando…"} />
            <StatusValue label="Migración de base" value={maintenance?.database_migration ?? "Pendiente de adoptar"} mono />
            <StatusValue label="Actualizaciones" value={maintenance?.update_source ?? "GitHub"} />
            <StatusValue label="Instalación directa" value={maintenance?.direct_install_allowed === false ? "Bloqueada" : "No disponible"} />
            <StatusValue label="Publicación" value={maintenance?.workflow_configured ? "GitHub Actions" : "Configuración pendiente"} />
            {maintenance && Object.entries(maintenance.packages).map(([name, version]) => (
              <StatusValue key={name} label={name} value={version ?? "No instalado"} mono />
            ))}
          </CardContent>
        </Card>
      )}

      {(historyOnly || activeTab === "history") && <Card className="gap-0 py-0">
        {!historyOnly && <CardHeader className="flex-row items-start justify-between gap-3 px-5 py-4">
          <div>
            <CardTitle>{historyOnly ? "Historial central DevOps" : "Últimas operaciones"}</CardTitle>
            <CardDescription>
              {historyOnly
                ? "Registro enviado por los equipos de los programadores."
                : "Registro de bajar, subir y publicar."}
            </CardDescription>
          </div>
          <ExcelDownloadButton onDownload={exportLogs} disabled={logTotal === 0} />
        </CardHeader>}
        <CardContent className={`space-y-3 px-5 pb-4 ${historyOnly ? "pt-4" : ""}`}>
          <StandardListToolbar embedded resultLabel={`${logTotal} operacion${logTotal === 1 ? "" : "es"} encontrada${logTotal === 1 ? "" : "s"}`} pagination={<ListPagination embedded compactWhenSinglePage page={logPage} pageSize={logPageSize} totalItems={logTotal} totalPages={logTotalPages} onPageChange={setLogPage} onPageSizeChange={(value) => { setLogPageSize(value); setLogPage(1); }} />} search={logSearch} onSearchChange={(value) => { setLogSearch(value); setLogPage(1); }} searchPlaceholder="Buscar acción, estado, mensaje, actor o commit..." filters={[
            { value: "all", label: "Todos", count: logCounts.all },
            { value: "success", label: "Exitosos", count: logCounts.success },
            { value: "failed", label: "Fallidos", count: logCounts.failed },
            { value: "cancelled", label: "Detenidos", count: logCounts.cancelled },
            { value: "publish", label: "Publicaciones", count: logCounts.publish },
          ]} activeFilter={logFilter} onFilterChange={(value) => { setLogFilter(value); setLogPage(1); }} resultCount={logTotal} totalCount={logCounts.all} />
          <button type="button" className="text-xs text-muted-foreground underline-offset-4 hover:underline" onClick={() => { setLogDirection((current) => current === "asc" ? "desc" : "asc"); setLogPage(1); }}>Fecha: {logDirection === "desc" ? "más reciente primero" : "más antigua primero"}</button>
          {visibleLogs.length === 0 ? (
            <p className="text-sm text-muted-foreground">No hay operaciones para los filtros actuales.</p>
          ) : (
            <div className="divide-y rounded-lg border">
              {visibleLogs.map((log) => (
                <div key={log.id} className="flex flex-col gap-1 p-3 sm:flex-row sm:items-center sm:justify-between">
                  <div>
                    <div className="flex flex-wrap items-center gap-2">
                      <p className="text-sm font-medium capitalize">{log.accion}</p>
                      {log.origen && <Badge variant="secondary">{log.origen}</Badge>}
                    </div>
                    <p className="text-xs text-muted-foreground">{log.mensaje}</p>
                    {log.actor && <p className="text-xs text-muted-foreground">Por {log.actor}</p>}
                  </div>
                  <div className="flex items-center gap-2 text-xs text-muted-foreground">
                    <Badge variant="outline">{log.estado}</Badge>
                    <span>{formatLimaDateTime(log.creado_en)}</span>
                  </div>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>}

      <AlertDialog open={cancelOpen} onOpenChange={setCancelOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>¿Detener el proceso activo?</AlertDialogTitle>
            <AlertDialogDescription>
              Se finalizará el comando y sus procesos secundarios. El repositorio puede requerir una revisión antes de volver a bajar, subir o publicar.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogAction onClick={() => setCancelOpen(false)}>Continuar proceso</AlertDialogAction>
            <Button variant="destructive" onClick={() => void cancelProcess()}>
              <Square className="fill-current" />
              Detener proceso
            </Button>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      <AlertDialog open={operationResult !== null} onOpenChange={(open) => !open && setOperationResult(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <div className={"mb-2 flex h-11 w-11 items-center justify-center rounded-full " + (
              operationResult?.kind === "success"
                ? "bg-emerald-100 text-emerald-700"
                : "bg-red-100 text-red-700"
            )}>
              {operationResult?.kind === "success"
                ? <CheckCircle2 className="h-6 w-6" />
                : <TerminalSquare className="h-6 w-6" />}
            </div>
            <AlertDialogTitle>{operationResult?.title}</AlertDialogTitle>
            <AlertDialogDescription className="space-y-2">
              <span className="block">{operationResult?.message}</span>
              <span className="block font-medium text-foreground">
                {operationResult?.confirmedFinished
                  ? "El proceso ya terminó; puedes cerrar este aviso o reintentarlo."
                  : "Se perdió la comunicación y no se puede confirmar si el servidor terminó. Consulta GitHub antes de reintentar."}
              </span>
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogAction onClick={() => setOperationResult(null)}>Entendido</AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      <Sheet open={publishOpen} onOpenChange={setPublishOpen}>
        <SheetContent className="sm:max-w-md">
          <SheetHeader>
            <SheetTitle>Confirmar publicación</SheetTitle>
            <SheetDescription>
              Elige qué parte del proyecto se validará y publicará en producción.
            </SheetDescription>
          </SheetHeader>

          <SheetBody className="space-y-7">
            <SheetSection>
              <div>
                <SheetSectionTitle>Alcance de la publicación</SheetSectionTitle>
                <SheetSectionDescription>Define qué servicios se validarán y actualizarán.</SheetSectionDescription>
              </div>
              <div className="space-y-3">
                <PublishOption
                  selected={publishTarget === "backend"}
                  icon={<Server className="h-5 w-5" />}
                  title="Solo backend"
                  description="Actualiza la API y reinicia el servicio. No compila ni reemplaza el frontend."
                  onClick={() => setPublishTarget("backend")}
                />
                <PublishOption
                  selected={publishTarget === "frontend"}
                  icon={<Monitor className="h-5 w-5" />}
                  title="Solo frontend"
                  description="Compila y publica el dist. El backend continúa funcionando sin reiniciarse."
                  onClick={() => setPublishTarget("frontend")}
                />
                <PublishOption
                  selected={publishTarget === "both"}
                  icon={<Layers3 className="h-5 w-5" />}
                  title="Backend y frontend"
                  description="Actualiza la API, reinicia el servicio y compila y publica el dist."
                  onClick={() => setPublishTarget("both")}
                />
              </div>
            </SheetSection>
            <SheetSection>
              <div>
                <SheetSectionTitle>Resumen</SheetSectionTitle>
                <SheetSectionDescription>Revisa el destino y el contenido antes de confirmar.</SheetSectionDescription>
              </div>
              <div className="space-y-3 rounded-xl border bg-muted/20 p-4 text-sm">
              <div className="flex justify-between gap-3">
                <span className="text-muted-foreground">Destino</span>
                <span className="font-medium">ABISSOL V2 · destino pendiente</span>
              </div>
              <div className="flex justify-between gap-3">
                <span className="text-muted-foreground">Commit</span>
                <span className="font-mono font-medium">{shortCommit(status?.local_commit)}</span>
              </div>
              <div className="flex justify-between gap-3">
                <span className="text-muted-foreground">Publicación</span>
                <span className="font-medium">
                  {publishTarget === "backend"
                    ? "Solo backend"
                    : publishTarget === "frontend"
                      ? "Solo frontend"
                  : "Backend y frontend"}
                </span>
              </div>
              </div>
            </SheetSection>
          </SheetBody>

          <SheetFooter>
            <Button variant="outline" onClick={() => setPublishOpen(false)}>
              Cancelar
            </Button>
            <Button
              onClick={() => {
                setPublishOpen(false);
                void runAction("publish", publishTarget);
              }}
              disabled={busy || !status?.can_publish}
            >
              <Rocket />
              Confirmar publicación
            </Button>
          </SheetFooter>
        </SheetContent>
      </Sheet>

      <Sheet open={filesOpen} onOpenChange={setFilesOpen}>
        <SheetContent className="sm:max-w-lg">
          <SheetHeader>
            <SheetTitle>
              {filesKind === "remote"
                ? "Archivos pendientes de bajar"
                : filesKind === "ahead"
                  ? "Archivos incluidos en los commits por subir"
                  : "Archivos locales pendientes"}
            </SheetTitle>
            <SheetDescription>
              {displayedFiles.length} archivo(s) se incluirán al {filesKind === "remote" ? "bajar" : "subir"} la actualización.
            </SheetDescription>
          </SheetHeader>
          <SheetBody className="space-y-3">
            {filesKind === "ahead" && Boolean(status?.ahead_commits.length) && (
              <div className="mb-5 space-y-2 rounded-xl border bg-muted/30 p-4">
                <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Commits pendientes</p>
                {status?.ahead_commits.map((commit) => (
                  <p key={commit} className="font-mono text-xs">{commit}</p>
                ))}
              </div>
            )}
            {displayedFiles.map((change, index) => {
              const detail = changeDetails(change);
              return (
                <div key={`${change}-${index}`} className="flex items-start gap-3 rounded-xl border bg-card/60 p-4 shadow-xs">
                  <FileCode2 className="mt-0.5 h-4 w-4 shrink-0 text-emerald-600" />
                  <div className="min-w-0 flex-1">
                    <p className="break-all font-mono text-xs">{detail.path}</p>
                    <p className="mt-1 text-xs text-muted-foreground">{detail.label}</p>
                  </div>
                  <Badge variant="outline" className="font-mono">{detail.code}</Badge>
                </div>
              );
            })}
            {!displayedFiles.length && (
              <p className="py-8 text-center text-sm text-muted-foreground">
                No hay archivos pendientes en este listado.
              </p>
            )}
          </SheetBody>
        </SheetContent>
      </Sheet>
    </main>
  );
}

function StatusValue({
  label,
  value,
  mono = false,
  onClick,
}: {
  label: string;
  value: string;
  mono?: boolean;
  onClick?: () => void;
}) {
  const content = (
    <>
      <p className="text-xs text-muted-foreground">{label}</p>
      <p className={`mt-1 text-sm font-semibold ${mono ? "font-mono" : ""}`}>{value}</p>
    </>
  );

  if (onClick) {
    return (
      <button
        type="button"
        className="cursor-pointer rounded-lg border bg-muted/30 px-3 py-2 text-left transition-colors hover:border-emerald-300 hover:bg-emerald-50/60"
        onClick={onClick}
      >
        {content}
      </button>
    );
  }

  return (
    <div className="rounded-lg border bg-muted/30 px-3 py-2">
      {content}
    </div>
  );
}

function DevopsTabButton({
  active,
  icon,
  children,
  onClick,
}: {
  active: boolean;
  icon: React.ReactNode;
  children: React.ReactNode;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      role="tab"
      aria-selected={active}
      onClick={onClick}
      className={`-mb-px flex shrink-0 items-center justify-center gap-2 border-b-2 px-4 py-3 text-sm font-medium transition-colors ${
        active
          ? "border-emerald-500 text-foreground"
          : "border-transparent text-muted-foreground hover:border-border hover:text-foreground"
      }`}
    >
      <span className="[&>svg]:size-4">{icon}</span>
      <span className="truncate">{children}</span>
    </button>
  );
}

function PublishOption({
  selected,
  icon,
  title,
  description,
  onClick,
}: {
  selected: boolean;
  icon: React.ReactNode;
  title: string;
  description: string;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`flex w-full items-start gap-3 rounded-xl border p-4 text-left transition-colors ${
        selected
          ? "border-slate-400 bg-slate-100 ring-1 ring-slate-300"
          : "hover:border-slate-300 hover:bg-slate-50"
      }`}
    >
      <span className={`rounded-lg p-2 ${selected ? "bg-white text-slate-800" : "bg-muted text-muted-foreground"}`}>
        {icon}
      </span>
      <span className="min-w-0 flex-1">
        <span className="block text-sm font-semibold">{title}</span>
        <span className="mt-1 block text-xs leading-5 text-muted-foreground">{description}</span>
      </span>
      <span className={`mt-2 h-4 w-4 rounded-full border ${selected ? "border-slate-700 bg-slate-700 ring-2 ring-white" : "border-slate-300"}`} />
    </button>
  );
}

function ActionCard({
  icon,
  title,
  description,
  button,
  loading,
  disabled,
  onClick,
}: {
  icon: React.ReactNode;
  title: string;
  description: string;
  button: string;
  loading: boolean;
  disabled: boolean;
  onClick: () => void;
}) {
  return (
    <Card className="gap-3 py-4">
      <CardHeader className="px-4 py-0">
        <div className="flex items-center gap-2">
          {icon}
          <CardTitle>{title}</CardTitle>
        </div>
        <CardDescription>{description}</CardDescription>
      </CardHeader>
      <CardContent className="px-4 pb-0">
        <Button className="w-full" variant="outline" disabled={disabled} onClick={onClick}>
          {loading && <Loader2 className="animate-spin" />}
          {button}
        </Button>
      </CardContent>
    </Card>
  );
}
