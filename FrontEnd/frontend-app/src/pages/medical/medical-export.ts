import type { ExportColumn } from "@/lib/table-tools";
import { toLimaInput } from "@/lib/dates";
type Row = Record<string, string | number | boolean | null>;
function dateValue(value: Row[string], timestamp = false) {
  if (!value) return null;
  const text = timestamp ? toLimaInput(String(value)) : String(value).slice(0, 10);
  return text ? new Date(text + (timestamp ? ":00Z" : "T00:00:00Z")) : null;
}
export function exportColumns(section: string, fallback: [string, (row: Row) => string][]): ExportColumn<Row>[] {
  const cols: ExportColumn<Row>[] = fallback.map(([header, value]) => ({ header, value }));
  if (section !== "emissions" && section !== "liquidations") return cols;
  for (const col of cols) {
    if (col.header === "Registrada") { col.value = row => dateValue(row.created_at, true); col.numberFormat = "dd/mm/yyyy hh:mm"; }
    if (col.header === "Importe" || col.header === "Ventas") { col.value = row => Number(row[section === "emissions" ? "price" : "sales_total"] || 0); col.numberFormat = "#,##0.00"; }
  }
  const dates = (key: string, header: string): ExportColumn<Row> => ({ header, value: row => dateValue(row[key]), numberFormat: "dd/mm/yyyy" });
  if (section === "emissions") {
    const index = cols.findIndex(col => col.header === "Vigencia");
    cols.splice(index, 1, dates("starts_on", "Inicio de vigencia"), dates("ends_on", "Fin de vigencia"));
    cols.push(dates("sale_date", "Fecha de emisión"));
  }
  return cols;
}
export function exportFooter(section: string, rows: Row[], columns: ExportColumn<Row>[]) {
  if (section !== "emissions" && section !== "liquidations") return undefined;
  const amount = rows.filter(row => row.status !== "cancelled").reduce((sum, row) => sum + Number(row[section === "emissions" ? "price" : "sales_total"] || 0), 0);
  return columns.map((col, index) => index === 0 ? "TOTAL (sin anulados)" : col.header === "Ventas" || col.header === "Importe" ? amount : null);
}
