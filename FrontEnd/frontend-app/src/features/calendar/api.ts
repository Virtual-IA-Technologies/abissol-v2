import api from "@/lib/api";
import type { CalendarEvent, CalendarEventWrite, CalendarLabel, CalendarPerson, CalendarStatus } from "./types";

export const calendarAPI = {
  events: async (params: { desde?: string; hasta?: string; buscar?: string; estado?: CalendarStatus | "todos"; asignado_id?: number }, signal?: AbortSignal) =>
    (await api.get<CalendarEvent[]>("/calendario/eventos", { params, signal })).data,
  notifications: async () => (await api.get<CalendarEvent[]>("/calendario/notificaciones")).data,
  people: async () => (await api.get<CalendarPerson[]>("/calendario/personas")).data,
  labels: async () => (await api.get<CalendarLabel[]>("/calendario/etiquetas")).data,
  create: async (payload: CalendarEventWrite) => (await api.post<CalendarEvent>("/calendario/eventos", payload)).data,
  update: async (id: number, payload: Partial<CalendarEventWrite> & { version: number }) =>
    (await api.put<CalendarEvent>(`/calendario/eventos/${id}`, payload)).data,
  remove: async (id: number) => { await api.delete(`/calendario/eventos/${id}`); },
  createLabel: async (nombre: string, color: string) =>
    (await api.post<CalendarLabel>("/calendario/etiquetas", { nombre, color })).data,
  removeLabel: async (id: number) => { await api.delete(`/calendario/etiquetas/${id}`); },
  exportIcs: async () => (await api.get<Blob>("/calendario/exportar.ics", { responseType: "blob" })).data,
};
