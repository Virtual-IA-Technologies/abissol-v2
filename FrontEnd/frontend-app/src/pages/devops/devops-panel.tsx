import { useCallback, useEffect, useState } from "react";
import axios from "axios";
import { RefreshCw, Upload, Download, Rocket } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { useAuth } from "@/context/AuthContext";
import { devopsAPI, type DevopsStatus, type DevopsLog } from "@/services/devopsService";

function errorMessage(error: unknown): string {
  if (axios.isAxiosError(error)) {
    const detail = error.response?.data?.detail;
    return typeof detail === "string" ? detail : detail?.message || error.message;
  }
  return error instanceof Error ? error.message : "No se pudo completar la operación.";
}

export default function DevopsPanel() {
  const { can } = useAuth();
  const [status, setStatus] = useState<DevopsStatus | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [terminal, setTerminal] = useState<string[]>([]);
  const [tab, setTab] = useState<"repository" | "logs">("repository");
  const [logs, setLogs] = useState<DevopsLog[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState("");
  const refresh = useCallback(async (remote = true) => {
    setBusy(true); setError("");
    try { setStatus((await devopsAPI.getStatus(remote)).status); }
    catch (error) { setError(errorMessage(error)); }
    finally { setBusy(false); }
  }, []);
  useEffect(() => { if (!import.meta.env.PROD) void refresh(false); }, [refresh]);
  useEffect(() => {
    if (!busy) return;
    let stopped = false;
    let timer: ReturnType<typeof setTimeout>;
    const poll = async () => {
      try { const result = await devopsAPI.getProgress(); if (!stopped) setTerminal(result.terminal); }
      catch { /* La acción principal informa el error. */ }
      if (!stopped) timer = setTimeout(poll, 1000);
    };
    void poll();
    return () => { stopped = true; clearTimeout(timer); };
  }, [busy]);
  useEffect(() => {
    if (tab !== "logs") return;
    let stopped = false;
    const timer = setTimeout(() => {
      devopsAPI.getLogs(page, search).then(result => {
        if (!stopped) { setLogs(result.items); setTotal(result.total); }
      }).catch(error => { if (!stopped) setError(errorMessage(error)); });
    }, 250);
    return () => { stopped = true; clearTimeout(timer); };
  }, [tab, page, search, busy]);
  async function execute(action: "pull" | "push" | "publish") {
    const labels = { pull: "Descargar origin/main", push: "Guardar y subir a origin/main", publish: "Publicar main en el servidor" };
    if (!window.confirm(`${labels[action]}?`)) return;
    setBusy(true); setError(""); setTerminal([]);
    try {
      const result = await devopsAPI.action(action, message);
      setStatus(result.status); setTerminal(result.terminal); setMessage("");
    } catch (error) { setError(errorMessage(error)); }
    finally { setBusy(false); }
  }
  return <div className="space-y-6 p-4 md:p-6">
    <div><h1 className="text-2xl font-semibold">Actualizaciones</h1>
      <p className="text-muted-foreground">Local → GitHub main → servidor</p></div>
    <div className="flex gap-2"><Button variant={tab === "repository" ? "default" : "outline"} onClick={() => setTab("repository")}>Repositorio</Button>
      <Button variant={tab === "logs" ? "default" : "outline"} onClick={() => setTab("logs")}>Historial</Button></div>
    {error && <p role="alert" className="rounded-lg border border-destructive p-3 text-destructive">{error}</p>}
    {tab === "repository" ? <>
      <Card><CardHeader><CardTitle>Rama única: main</CardTitle></CardHeader><CardContent className="space-y-4">
        {import.meta.env.PROD ? <p>Las actualizaciones se ejecutan desde el entorno local. Consulta las operaciones en Historial.</p> : <>
          <p role="status">{busy ? "Operación en curso…" : status?.message || "Consulta el estado del repositorio."}</p>
          <Button variant="outline" disabled={busy} onClick={() => void refresh()}><RefreshCw className={busy ? "animate-spin" : ""}/>Actualizar estado</Button>
          {status && <><p className="text-sm text-muted-foreground">{status.changes.length} archivos pendientes ? {status.ahead} commits por subir ? {status.behind} por descargar</p>
            <p className="text-sm">Commit local: <code>{status.local_commit.slice(0, 12)}</code></p>
            {status.changes.length > 0 && <details><summary className="cursor-pointer">Archivos modificados</summary><pre className="mt-2 max-h-64 overflow-auto text-xs">{status.changes.join("\n")}</pre></details>}
          </>}
          <label className="block space-y-2"><span>Descripción de los cambios</span><Input value={message} onChange={event => setMessage(event.target.value)} maxLength={180} placeholder="Describe esta actualización" disabled={busy}/></label>
          <div className="flex flex-wrap gap-2">
            <Button variant="outline" disabled={busy || !status?.can_pull || !can("devops", "editor")} onClick={() => void execute("pull")}><Download/>Descargar main</Button>
            <Button disabled={busy || !status?.can_push || !can("devops", "gestor") || Boolean(status?.changes.length && !message.trim())} onClick={() => void execute("push")}><Upload/>Subir a GitHub</Button>
            <Button variant="outline" disabled={busy || !status?.can_publish || !can("devops", "gestor")} onClick={() => void execute("publish")}><Rocket/>Publicar servidor</Button>
          </div>
          {!status?.deployment_configured && <p className="text-sm text-muted-foreground">Publicación pendiente de configurar servidor y dominio.</p>}
        </>}
      </CardContent></Card>
      {terminal.length > 0 && <Card><CardHeader><CardTitle>Salida de la operación</CardTitle></CardHeader><CardContent><pre aria-live="polite" className="max-h-96 overflow-auto whitespace-pre-wrap rounded-lg bg-muted p-4 text-xs">{terminal.join("\n")}</pre></CardContent></Card>}
    </> : <Card><CardHeader><CardTitle>Historial de actualizaciones</CardTitle></CardHeader><CardContent className="space-y-4">
      <Input aria-label="Buscar en historial" placeholder="Buscar operación, resultado o commit" value={search} onChange={event => { setSearch(event.target.value); setPage(1); }}/>
      {logs.length ? logs.map(log => <details key={log.id} className="rounded-lg border p-3"><summary className="cursor-pointer">{log.accion} · {log.estado} · {log.creado_en ? new Date(log.creado_en).toLocaleString("es-PE", { timeZone: "America/Lima" }) : ""}</summary><p className="mt-2">{log.mensaje}</p><pre className="mt-2 max-h-64 overflow-auto whitespace-pre-wrap text-xs">{log.salida}</pre></details>) : <p>No hay operaciones para mostrar.</p>}
      <div className="flex items-center gap-3"><Button variant="outline" disabled={page <= 1} onClick={() => setPage(page - 1)}>Anterior</Button><span>{page} / {Math.max(1, Math.ceil(total / 10))} · {total} operaciones</span><Button variant="outline" disabled={page * 10 >= total} onClick={() => setPage(page + 1)}>Siguiente</Button></div>
    </CardContent></Card>}
  </div>;
}
