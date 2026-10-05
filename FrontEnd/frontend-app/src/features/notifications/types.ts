export type NotificationItem = {
  id: number;
  event_type: string;
  source: string;
  severity: "info" | "warning" | "critical";
  title: string;
  message: string;
  entity: string | null;
  entity_id: string | null;
  url: string | null;
  read_at: string | null;
  created_at: string;
};

export type NotificationType = {
  event_type: string;
  source: string;
  label: string;
  severity: string;
  enabled: boolean;
};
