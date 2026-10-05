export const LIMA_TIME_ZONE = "America/Lima";

function parseApiDateTime(value: string): Date {
  const normalized = /(?:Z|[+-]\d{2}:\d{2})$/i.test(value) ? value : `${value}Z`;
  return new Date(normalized);
}

export function toLimaInput(value: string | null | undefined): string {
  if (!value) return "";
  const date = parseApiDateTime(value);
  if (Number.isNaN(date.getTime())) return "";
  const parts = new Intl.DateTimeFormat("en-CA", {
    timeZone: LIMA_TIME_ZONE,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hourCycle: "h23",
  }).formatToParts(date);
  const part = (type: Intl.DateTimeFormatPartTypes) => parts.find((item) => item.type === type)?.value;
  return `${part("year")}-${part("month")}-${part("day")}T${part("hour")}:${part("minute")}`;
}

export function fromLimaInput(value: string | null | undefined): string | null {
  return value ? new Date(`${value}-05:00`).toISOString() : null;
}

export function formatLimaDateTime(value: string | null | undefined): string {
  if (!value) return "—";
  const date = parseApiDateTime(value);
  if (Number.isNaN(date.getTime())) return "—";
  return new Intl.DateTimeFormat("es-PE", {
    timeZone: LIMA_TIME_ZONE,
    dateStyle: "short",
    timeStyle: "medium",
  }).format(date);
}
