import { useCallback, useEffect, useRef, useState, type PointerEvent as ReactPointerEvent } from "react";
import { Bell, ExternalLink, FileText, Navigation, Send, Trash2 } from "lucide-react";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Sheet, SheetBody, SheetContent, SheetDescription, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { useAuth } from "@/context/AuthContext";
import { settingsAPI } from "@/features/settings/api";
import type { AviChatMessage, AviFallbackReason, AviPublicSettings, AviQuickPrompt } from "@/features/settings/types";
import { useNotifications } from "@/features/notifications/notification-context";
import type { NotificationItem } from "@/features/notifications/types";
import type { GlobalSearchResult } from "@/features/wolverine/types";

const AVI_AVATAR_URL = "/avi-avatar-ui.png";
const AVI_LAUNCHER_POSITION_KEY = "abissol-avi-launcher-position";
/** Máximo de mensajes del hilo que se guardan en backend por usuario. */
const MAX_THREAD_MESSAGES = 40;

type AviConversationMessage = {
  id: number;
  role: "user" | "assistant";
  text: string;
  source?: string;
  results?: GlobalSearchResult[];
  notices?: NotificationItem[];
  capability?: string;
  fallbackReason?: AviFallbackReason;
  streaming?: boolean;
};

function AviAvatar({ name, className }: { name: string; className: string }) {
  return <span className={`inline-flex shrink-0 items-center justify-center overflow-hidden rounded-full bg-gradient-to-br from-violet-100 to-teal-100 ${className}`}><img src={AVI_AVATAR_URL} alt={`Avatar de ${name}`} draggable={false} className="size-full object-contain pointer-events-none" /></span>;
}

function useAviLauncherPosition() {
  const [position, setPosition] = useState(() => {
    try {
      const stored = JSON.parse(localStorage.getItem(AVI_LAUNCHER_POSITION_KEY) ?? "null") as { x?: unknown; y?: unknown } | null;
      return stored && Number.isFinite(stored.x) && Number.isFinite(stored.y)
        ? { x: Number(stored.x), y: Number(stored.y) }
        : { x: 0, y: 0 };
    } catch { return { x: 0, y: 0 }; }
  });
  const positionRef = useRef(position);
  const suppressClick = useRef(false);
  const drag = useRef<{
    pointerId: number; x: number; y: number; startX: number; startY: number;
    minX: number; maxX: number; minY: number; maxY: number; moved: boolean;
  } | null>(null);
  const update = useCallback((next: { x: number; y: number }, persist = false) => {
    positionRef.current = next;
    setPosition(next);
    if (persist) try { localStorage.setItem(AVI_LAUNCHER_POSITION_KEY, JSON.stringify(next)); } catch { /* Preferencia opcional. */ }
  }, []);
  const keepVisible = useCallback((element: HTMLElement | null) => {
    if (!element) return;
    const bounds = element.getBoundingClientRect();
    const margin = 8;
    const next = { x: positionRef.current.x, y: positionRef.current.y };
    if (bounds.left < margin) next.x += margin - bounds.left;
    if (bounds.right > window.innerWidth - margin) next.x -= bounds.right - (window.innerWidth - margin);
    if (bounds.top < margin) next.y += margin - bounds.top;
    if (bounds.bottom > window.innerHeight - margin) next.y -= bounds.bottom - (window.innerHeight - margin);
    if (next.x !== positionRef.current.x || next.y !== positionRef.current.y) update(next, true);
  }, [update]);
  const onPointerDown = (event: ReactPointerEvent<HTMLButtonElement>) => {
    if (event.button !== 0) return;
    const bounds = event.currentTarget.getBoundingClientRect();
    const margin = 8;
    drag.current = {
      pointerId: event.pointerId, x: event.clientX, y: event.clientY,
      startX: positionRef.current.x, startY: positionRef.current.y,
      minX: positionRef.current.x + margin - bounds.left,
      maxX: positionRef.current.x + window.innerWidth - margin - bounds.right,
      minY: positionRef.current.y + margin - bounds.top,
      maxY: positionRef.current.y + window.innerHeight - margin - bounds.bottom,
      moved: false,
    };
    event.currentTarget.setPointerCapture(event.pointerId);
  };
  const onPointerMove = (event: ReactPointerEvent<HTMLButtonElement>) => {
    const current = drag.current;
    if (!current || current.pointerId !== event.pointerId) return;
    if (Math.hypot(event.clientX - current.x, event.clientY - current.y) > 4) current.moved = true;
    if (!current.moved) return;
    event.preventDefault();
    update({
      x: Math.max(current.minX, Math.min(current.maxX, current.startX + event.clientX - current.x)),
      y: Math.max(current.minY, Math.min(current.maxY, current.startY + event.clientY - current.y)),
    });
  };
  const finishPointer = (event: ReactPointerEvent<HTMLButtonElement>, suppress: boolean) => {
    if (drag.current?.pointerId !== event.pointerId) return;
    suppressClick.current = suppress && drag.current.moved;
    if (drag.current.moved) update(positionRef.current, true);
    drag.current = null;
  };
  const consumeClick = () => {
    const consumed = suppressClick.current;
    suppressClick.current = false;
    return consumed;
  };
  return {
    position, keepVisible, consumeClick,
    dragHandlers: {
      onPointerDown,
      onPointerMove,
      onPointerUp: (event: ReactPointerEvent<HTMLButtonElement>) => finishPointer(event, true),
      onPointerCancel: (event: ReactPointerEvent<HTMLButtonElement>) => finishPointer(event, false),
    },
  };
}

function limaClock() {
  const parts = new Intl.DateTimeFormat("en-CA", { timeZone: "America/Lima", year: "numeric", month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit", hourCycle: "h23" }).formatToParts();
  const value = Object.fromEntries(parts.map((part) => [part.type, part.value]));
  return { date: `${value.year}-${value.month}-${value.day}`, time: `${value.hour}:${value.minute}` };
}

function inQuietHours(now: string, start: string, end: string) {
  return start < end ? now >= start && now < end : now >= start || now < end;
}

/** Icono de acceso rápido según la capacidad asociada. */
function QuickPromptIcon({ capability }: { capability: AviQuickPrompt["capability"] }) {
  if (capability === "notifications") return <Bell className="size-4" />;
  if (capability === "document_management") return <FileText className="size-4" />;
  return <Navigation className="size-4" />;
}

export function AviAssistant() {
  const navigate = useNavigate();
  const { token, user, can } = useAuth();
  const { unread, markRead } = useNotifications();
  const launcherRef = useRef<HTMLButtonElement>(null);
  const queryInput = useRef<HTMLInputElement>(null);
  const selectedContext = useRef<GlobalSearchResult | null>(null);
  const focusInput = useCallback(() => queryInput.current?.focus({ preventScroll: true }), []);
  const conversationViewport = useRef<HTMLDivElement>(null);
  const conversationEnd = useRef<HTMLDivElement>(null);
  const messageSequence = useRef(0);
  const responseRun = useRef(0);
  const { position: launcherPosition, keepVisible, consumeClick, dragHandlers } = useAviLauncherPosition();
  const [configuration, setConfiguration] = useState<AviPublicSettings | null>(null);
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [conversation, setConversation] = useState<AviConversationMessage[]>([]);
  const [busy, setBusy] = useState(false);
  const [thinking, setThinking] = useState(false);
  const [threadLoaded, setThreadLoaded] = useState(false);

  // Carga configuración pública al iniciar sesión.
  useEffect(() => {
    let active = true;
    if (!token) { setConfiguration(null); return; }
    settingsAPI.getAviContext().then((value) => { if (active) setConfiguration(value); }).catch(() => { if (active) setConfiguration(null); });
    return () => { active = false; };
  }, [token]);

  // Carga el hilo persistido en backend cuando el panel se abre por primera vez.
  useEffect(() => {
    let active = true;
    responseRun.current += 1;
    setThreadLoaded(false);
    setConversation([]);
    selectedContext.current = null;
    setBusy(false);
    setThinking(false);
    if (!token) return;
    settingsAPI.getAviThread().then((thread) => {
      if (!active) return;
      if (thread.messages.length > 0) {
        const restored: AviConversationMessage[] = thread.messages.map((m) => ({
          id: Date.now() * 100 + ++messageSequence.current,
          role: m.role,
          text: m.content,
          results: m.results,
          capability: m.capability ?? undefined,
          fallbackReason: (m.fallback_reason as AviFallbackReason | null) ?? undefined,
        }));
        setConversation(restored);
      }
      setThreadLoaded(true);
    }).catch(() => { if (active) setThreadLoaded(true); });
    return () => { active = false; responseRun.current += 1; };
  }, [token, user?.id]);

  // Persiste el hilo en backend cuando cambia la conversación (debounced ~1.5s).
  useEffect(() => {
    if (!threadLoaded || busy || conversation.length === 0) return;
    const timer = window.setTimeout(() => {
      const messages = conversation
        .slice(-MAX_THREAD_MESSAGES)
        .filter((m) => m.text.trim())
        .map((m) => ({
          role: m.role,
          content: m.text.slice(0, 2000),
          results: m.results ?? [],
          capability: m.capability ?? null,
          fallback_reason: m.fallbackReason ?? null,
        }));
      settingsAPI.saveAviThread(messages).catch(() => { /* silencioso: el hilo sigue en memoria */ });
    }, 1500);
    return () => window.clearTimeout(timer);
  }, [conversation, threadLoaded, token, busy]);

  // Iniciativa diaria: muestra un toast una vez por fecha/usuario.
  useEffect(() => {
    if (!configuration?.enabled || !configuration.initiative.enabled || !configuration.initiative.daily_summary || unread === 0) return;
    const now = limaClock();
    if (now.time < configuration.initiative.daily_summary_time) return;
    if (configuration.initiative.quiet_hours_enabled && inQuietHours(now.time, configuration.initiative.quiet_hours_start, configuration.initiative.quiet_hours_end)) return;
    const key = `abissol-avi-summary-${user?.id ?? "session"}-${now.date}`;
    if (localStorage.getItem(key)) return;
    localStorage.setItem(key, "shown");
    toast.info(`${configuration.assistant_name} preparó tu resumen`, { description: `Tienes ${unread} notificación${unread === 1 ? "" : "es"} sin leer.`, action: { label: "Revisar", onClick: () => setOpen(true) } });
  }, [configuration, unread, user?.id]);

  useEffect(() => {
    const keepLauncherOnScreen = () => keepVisible(launcherRef.current);
    keepLauncherOnScreen();
    window.addEventListener("resize", keepLauncherOnScreen);
    return () => window.removeEventListener("resize", keepLauncherOnScreen);
  }, [keepVisible]);

  useEffect(() => {
    if (open) return;
    const frame = requestAnimationFrame(() => keepVisible(launcherRef.current));
    return () => cancelAnimationFrame(frame);
  }, [open, keepVisible]);

  useEffect(() => () => { responseRun.current += 1; }, []);

  useEffect(() => {
    if (!open) return;
    const frame = requestAnimationFrame(() => {
      const viewport = conversationViewport.current;
      if (viewport) viewport.scrollTop = viewport.scrollHeight;
    });
    return () => cancelAnimationFrame(frame);
  }, [conversation, thinking, open]);

  const revealResponse = async (
    run: number,
    text: string,
    source: string,
    nextResults: GlobalSearchResult[] = [],
    nextNotices: NotificationItem[] = [],
    metadata: { capability?: string; fallbackReason?: AviFallbackReason } = {},
  ) => {
    if (responseRun.current !== run) return;
    setThinking(false);
    const id = Date.now() * 100 + ++messageSequence.current;
    const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    setConversation((messages) => [...messages, {
      id, role: "assistant", text: reducedMotion ? text : "", streaming: !reducedMotion,
      results: reducedMotion ? nextResults : [], notices: reducedMotion ? nextNotices : [],
      capability: metadata.capability, fallbackReason: metadata.fallbackReason,
    }]);
    if (!reducedMotion) {
      const duration = Math.min(3500, Math.max(650, text.length * 12));
      const step = Math.max(1, Math.ceil(text.length / (duration / 25)));
      for (let length = step; length < text.length + step; length += step) {
        await new Promise((resolve) => window.setTimeout(resolve, 25));
        if (responseRun.current !== run) return;
        setConversation((messages) => messages.map((message) => message.id === id
          ? { ...message, text: text.slice(0, length) } : message));
      }
      for (let length = 1; length <= nextResults.length; length++) {
        if (responseRun.current !== run) return;
        setConversation((messages) => messages.map((message) => message.id === id
          ? { ...message, results: nextResults.slice(0, length) } : message));
        if (length < nextResults.length) await new Promise((resolve) => window.setTimeout(resolve, 100));
      }
    }
    if (responseRun.current !== run) return;
    setConversation((messages) => messages.map((message) => message.id === id
      ? { ...message, source, streaming: false, notices: nextNotices } : message));
    focusInput();
  };

  if (!configuration?.enabled) return null;

  const ask = async (text = query) => {
    const question = text.trim();
    if (!question || busy) return;
    const run = ++responseRun.current;
    const history: AviChatMessage[] = conversation.slice(-12).map((message) => {
      let content = message.text;
      if (message.results?.length) {
        content += "\n[Resultados mostrados al usuario: " + message.results.map(r => r.title).join(", ") + "]";
      }
      return {
        role: message.role,
        content: content.slice(0, 2000),
        capability: message.capability ?? null,
        fallback_reason: message.fallbackReason ?? null,
      };
    }).filter((message) => message.content.trim().length > 0);
    const userMessage: AviConversationMessage = {
      id: Date.now() * 100 + ++messageSequence.current,
      role: "user",
      text: question,
    };
    setQuery("");
    setConversation((messages) => [...messages, userMessage]);
    setBusy(true);
    setThinking(true);
    focusInput();
    try {
      const previousResults = selectedContext.current ? [selectedContext.current]
        : [...conversation].reverse().find((message) => message.results?.length)?.results ?? [];
      const response = await settingsAPI.askAgent(question, history, previousResults);
      if (response.results.length) selectedContext.current = null;
      await revealResponse(run, response.message, response.source, response.results, [],
        { capability: response.capability ?? undefined });
      if (responseRun.current === run && response.navigate_to) {
        selectedContext.current = response.results[0] ?? null;
        navigate(response.navigate_to);
        requestAnimationFrame(focusInput);
      }
    } catch {
      await revealResponse(run, "Tuve un inconveniente al consultar la información. No realicé ningún cambio; podemos intentarlo nuevamente.", "AVI");
    } finally {
      if (responseRun.current === run) { setBusy(false); setThinking(false); }
    }
  };

  const go = (url: string, result?: GlobalSearchResult) => {
    selectedContext.current = result ?? null;
    navigate(url);
    setOpen(true);
    requestAnimationFrame(focusInput);
  };

  const clearConversation = async () => {
    responseRun.current += 1;
    setConversation([]);
    setThinking(false);
    setBusy(false);
    setQuery("");
    selectedContext.current = null;
    requestAnimationFrame(focusInput);
    settingsAPI.clearAviThread().catch(() => { /* silencioso */ });
  };

  // Filtra los quick_prompts del backend según capacidades activas y permisos Wolverine.
  const visibleQuickPrompts = configuration.quick_prompts.filter((qp) => {
    if (qp.capability && !configuration.capabilities[qp.capability as keyof typeof configuration.capabilities]) return false;
    if (qp.wolverine_slug && !can(qp.wolverine_slug)) return false;
    return true;
  });

  return <>
    {!open && <button ref={launcherRef} type="button" {...dragHandlers} onClick={(event) => { if (consumeClick()) { event.preventDefault(); return; } setOpen(true); }} style={{ transform: `translate(${launcherPosition.x}px, ${launcherPosition.y}px)` }} aria-label={`Abrir ${configuration.assistant_name}`} title={`${configuration.assistant_name} · arrastra para mover`} className="fixed bottom-5 right-5 z-40 flex size-16 cursor-move touch-none select-none items-center justify-center rounded-full border-2 border-white bg-gradient-to-br from-violet-100 to-teal-100 p-0.5 shadow-xl transition-shadow hover:shadow-2xl focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-500 focus-visible:ring-offset-2 dark:border-slate-800">
      <AviAvatar name={configuration.assistant_name} className="size-full" />{unread > 0 && configuration.capabilities.notifications && <span className="absolute -right-1 -top-1 flex min-w-5 items-center justify-center rounded-full bg-red-500 px-1 text-[10px] font-semibold leading-5 text-white">{unread > 99 ? "99+" : unread}</span>}
    </button>}
    <Sheet open={open} onOpenChange={setOpen}><SheetContent className="w-full sm:max-w-xl" onOpenAutoFocus={(event) => { event.preventDefault(); requestAnimationFrame(focusInput); }}><SheetHeader><div className="flex items-center gap-3"><AviAvatar name={configuration.assistant_name} className="size-11 border border-violet-200" /><div className="min-w-0 flex-1"><SheetTitle>{configuration.assistant_name} <span className="font-normal text-muted-foreground text-sm">(Asistente Virtual Inteligente)</span></SheetTitle><SheetDescription className="sr-only">Asistente virtual inteligente</SheetDescription></div></div></SheetHeader><SheetBody className="flex min-h-0 flex-1 flex-col overflow-hidden p-0">
      <div ref={conversationViewport} className="min-h-0 flex-1 space-y-5 overflow-y-auto px-6 py-5 sm:px-8">
      {conversation.length === 0 && <div className="flex items-end gap-2"><AviAvatar name={configuration.assistant_name} className="size-8" /><div className="rounded-2xl rounded-bl-sm border bg-violet-50/60 p-4 text-sm text-violet-950 shadow-sm dark:bg-violet-950/20 dark:text-violet-100">{configuration.welcome_message}</div></div>}
      {visibleQuickPrompts.length > 0 && <div className="flex flex-wrap gap-2">
        {visibleQuickPrompts.map((qp, index) => (
          <Button key={index} size="sm" variant="outline" disabled={busy} onClick={() => void ask(qp.prompt)}>
            <QuickPromptIcon capability={qp.capability} />{qp.label}
          </Button>
        ))}
      </div>}
      <div className="space-y-4">
        {conversation.map((message) => <div data-avi-role={message.role} key={message.id} className={`flex items-end gap-2 ${message.role === "user" ? "justify-end" : "justify-start"}`}>
          {message.role === "assistant" && <AviAvatar name={configuration.assistant_name} className="size-8" />}
          <div className={`max-w-[88%] rounded-2xl px-4 py-3 text-sm shadow-sm ${message.role === "user" ? "rounded-br-sm bg-violet-700 text-white" : "rounded-bl-sm border bg-card"}`}>
            <p data-avi-text className="whitespace-pre-wrap">{message.text}{message.streaming && <span className="ml-0.5 inline-block h-4 w-0.5 animate-pulse bg-violet-600 align-text-bottom" aria-hidden="true" />}</p>
            {message.results && message.results.length > 0 && <div className="mt-3 space-y-2">{message.results.map((result) => <button key={result.id} type="button" onClick={() => go(result.url, result)} className="flex w-full animate-in items-center gap-3 rounded-xl border bg-background p-3 text-left transition duration-300 fade-in slide-in-from-bottom-1 hover:bg-muted"><span className="flex size-9 shrink-0 items-center justify-center rounded-lg bg-violet-100 text-violet-700"><ExternalLink className="size-4" /></span><span className="min-w-0 flex-1"><strong className="block truncate text-sm">{result.title}</strong><span className="block truncate text-xs text-muted-foreground">{result.source} · {result.subtitle}</span></span></button>)}</div>}
            {message.notices && message.notices.length > 0 && <div className="mt-3 space-y-2">{message.notices.map((item) => <div key={item.id} className="animate-in rounded-xl border bg-background p-3 duration-300 fade-in slide-in-from-bottom-1"><div className="flex items-start justify-between gap-3"><div><strong className="block">{item.title}</strong><span className="text-xs text-muted-foreground">{item.message}</span></div><Button size="sm" variant="ghost" onClick={() => { void markRead(item.id); if (item.url) go(item.url); }}>{item.url ? "Abrir" : "Leer"}</Button></div></div>)}</div>}
            {message.notices && message.notices.length > 0 && <Button variant="link" className="mt-2 h-auto p-0 text-xs" onClick={() => go("/plataforma/sistema/notificaciones")}>Abrir buzón completo</Button>}
          </div>
        </div>)}
        {thinking && <div className="flex items-end gap-2" aria-live="polite"><AviAvatar name={configuration.assistant_name} className="size-8" /><div className="flex items-center gap-1 rounded-2xl rounded-bl-sm border bg-card px-3 py-2 shadow-sm" aria-label={`${configuration.assistant_name} está escribiendo`}>{[0, 1, 2].map((index) => <span key={index} className="size-1.5 animate-bounce rounded-full bg-violet-600" style={{ animationDelay: `${index * 120}ms` }} />)}</div></div>}
        <div ref={conversationEnd} />
      </div>
      </div>
      <div className="shrink-0 border-t bg-background px-6 pb-4 pt-4 sm:px-8"><form className="flex gap-2" onSubmit={(event) => { event.preventDefault(); void ask(); }}><Button type="button" size="icon" variant="ghost" className="shrink-0 text-muted-foreground hover:text-destructive" disabled={busy || conversation.length === 0} onClick={() => void clearConversation()} aria-label="Iniciar una conversación nueva" title="Nueva conversación"><Trash2 className="size-4" /></Button><Input ref={queryInput} aria-label="Escribe tu pregunta a AVI" value={query} maxLength={1000} onChange={(event) => setQuery(event.target.value)} placeholder="Escribe tu pregunta…" /><Button type="submit" size="icon" disabled={busy || query.trim().length < 2} aria-label="Enviar a AVI"><Send className="size-4" /></Button></form></div>
    </SheetBody></SheetContent></Sheet>
  </>;
}
