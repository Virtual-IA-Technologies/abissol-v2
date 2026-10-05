import { useState } from "react";
import { CalendarDays } from "lucide-react";
import { useNavigate } from "react-router-dom";

import { Button } from "@/components/ui/button";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { calendarAPI } from "@/features/calendar/api";
import type { CalendarEvent } from "@/features/calendar/types";
import { formatLimaDateTime } from "@/lib/dates";

export function CalendarQuickPopover() {
  const navigate = useNavigate();
  const [events, setEvents] = useState<CalendarEvent[]>([]);
  const [loaded, setLoaded] = useState(false);
  const load = (open: boolean) => { if (open && !loaded) void calendarAPI.notifications().then((items) => { setEvents(items.filter((item) => item.categoria === "proximo").slice(0, 5)); setLoaded(true); }); };
  return <Popover onOpenChange={load}><PopoverTrigger asChild><button type="button" aria-label="Abrir agenda rápida" title="Agenda rápida" className="hidden size-9 items-center justify-center rounded-md text-muted-foreground hover:bg-muted hover:text-foreground sm:flex"><CalendarDays className="size-4" /></button></PopoverTrigger><PopoverContent align="end" className="w-80 p-0"><div className="border-b p-4"><strong className="text-sm">Próximos eventos</strong><p className="text-xs text-muted-foreground">Tu agenda de los siguientes siete días.</p></div><div className="max-h-80 divide-y overflow-y-auto">{events.length ? events.map((event) => <button key={event.id} type="button" onClick={() => navigate("/plataforma/sistema/calendario", { state: { calendarEventId: event.id } })} className="block w-full p-3 text-left hover:bg-muted/50"><span className="block truncate text-sm font-medium">{event.titulo}</span><span className="text-xs text-muted-foreground">{formatLimaDateTime(event.inicio)}</span></button>) : <p className="p-5 text-center text-sm text-muted-foreground">Sin próximos eventos.</p>}</div><div className="border-t p-2"><Button variant="ghost" size="sm" className="w-full" onClick={() => navigate("/plataforma/sistema/calendario")}>Ver calendario completo</Button></div></PopoverContent></Popover>;
}
