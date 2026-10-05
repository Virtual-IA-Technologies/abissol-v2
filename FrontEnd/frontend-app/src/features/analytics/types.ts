export type MetricFormat = "integer" | "bytes" | "currency";
export interface MetricCardData {
  key: string; label: string; value: number; description: string; format: MetricFormat;
  icon: "activity" | "alert" | "bell" | "boxes" | "calendar" | "clock" | "shield" | "users";
  tone: "amber" | "blue" | "cyan" | "emerald" | "indigo" | "red"; url: string;
}
export interface MetricPoint { label: string; value: number }
export interface MetricChartData { key: string; title: string; description: string; type: "bar" | "line" | "donut"; format?: MetricFormat; points: MetricPoint[]; url: string | null }
export interface DashboardMetrics { generated_at: string; cards: MetricCardData[]; charts: MetricChartData[] }
export interface AuditStatistics { days: number; from: string; to: string; cards: MetricCardData[]; charts: MetricChartData[] }
