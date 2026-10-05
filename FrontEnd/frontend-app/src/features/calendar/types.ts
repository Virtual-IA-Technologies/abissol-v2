export type CalendarStatus = "pendiente" | "confirmado" | "en_progreso" | "completado" | "cancelado";
export type CalendarPriority = "baja" | "media" | "alta" | "urgente";
export type CalendarVisibility = "personal" | "equipo";

export type CalendarPerson = { id: number; nombre: string; username: string };
export type CalendarLabel = { id: number; nombre: string; color: string; is_active: boolean };
export type CalendarReminder = { id?: number; minutos_antes: number; canal: "interno" | "correo" };

export type CalendarEvent = {
  id: number; titulo: string; descripcion: string | null; inicio: string; fin: string;
  todo_el_dia: boolean; estado: CalendarStatus; prioridad: CalendarPriority;
  visibilidad: CalendarVisibility; ubicacion: string | null; propietario: CalendarPerson;
  asignados: CalendarPerson[]; etiquetas: CalendarLabel[]; recordatorios: CalendarReminder[];
  origen_modulo: string | null; origen_tipo: string | null; origen_id: string | null;
  origen_url: string | null; version: number; created_at: string; updated_at: string;
  categoria?: "vencido" | "proximo";
};

export type CalendarEventWrite = {
  titulo: string; descripcion: string | null; inicio: string; fin: string; todo_el_dia: boolean;
  estado: CalendarStatus; prioridad: CalendarPriority; visibilidad: CalendarVisibility;
  ubicacion: string | null; asignado_ids: number[]; etiqueta_ids: number[];
  recordatorios: Omit<CalendarReminder, "id">[]; origen_modulo: string | null;
  origen_tipo: string | null; origen_id: string | null; origen_url: string | null;
};
