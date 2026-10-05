export type SortDirection = "asc" | "desc";
export type SortValue = string | number | boolean | Date | null | undefined;

export function compareTableValues(left: SortValue, right: SortValue, direction: SortDirection) {
  const factor = direction === "asc" ? 1 : -1;
  if (left == null && right == null) return 0;
  if (left == null) return 1;
  if (right == null) return -1;
  if (typeof left === "number" && typeof right === "number") return (left - right) * factor;
  if (left instanceof Date && right instanceof Date) return (left.getTime() - right.getTime()) * factor;
  return String(left).localeCompare(String(right), "es", { numeric: true, sensitivity: "base" }) * factor;
}

export function nextSort<Key extends string>(
  currentKey: Key,
  currentDirection: SortDirection,
  selectedKey: Key,
): [Key, SortDirection] {
  return selectedKey === currentKey
    ? [currentKey, currentDirection === "asc" ? "desc" : "asc"]
    : [selectedKey, "asc"];
}

export function includesSearch(values: Array<unknown>, query: string) {
  const normalized = query.trim().toLocaleLowerCase("es");
  if (!normalized) return true;
  return values.some((value) => String(value ?? "").toLocaleLowerCase("es").includes(normalized));
}

export type ExportCell = string | number | boolean | null | undefined;

export interface ExportColumn<Row> {
  header: string;
  value: (row: Row) => ExportCell;
  width?: number;
  numberFormat?: string;
}

export interface ExcelReportOptions {
  organizationName: string;
  criteria: Record<string, ExportCell>;
  footer?: ExportCell[];
}

function safeExcelCell(value: ExportCell) {
  if (value == null) return "";
  if (typeof value !== "string") return value;
  return /^[=+\-@]/.test(value) ? `'${value}` : value;
}

function filenamePart(value: unknown) {
  return String(value ?? "")
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLocaleLowerCase("es")
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 36);
}

function limaTimestamp(date: Date) {
  const parts = new Intl.DateTimeFormat("en-CA", {
    timeZone: "America/Lima", year: "numeric", month: "2-digit", day: "2-digit",
    hour: "2-digit", minute: "2-digit", hourCycle: "h23",
  }).formatToParts(date);
  const part = (type: Intl.DateTimeFormatPartTypes) => parts.find((item) => item.type === type)?.value ?? "00";
  return `${part("year")}-${part("month")}-${part("day")}_${part("hour")}${part("minute")}`;
}

function excelFileName(filename: string, options: ExcelReportOptions, generatedAt: Date) {
  const cleanName = filenamePart(filename.replace(/\.(csv|xlsx)$/i, "")) || "reporte";
  const institution = filenamePart(options.organizationName);
  const criteria = Object.entries(options.criteria)
    .filter(([, value]) => value !== null && value !== undefined && String(value).trim() !== "")
    .map(([key, value]) => `${filenamePart(key)}-${filenamePart(value)}`)
    .filter(Boolean)
    .join("_");
  return `${[cleanName, institution, criteria].filter(Boolean).join("_").slice(0, 180)}_${limaTimestamp(generatedAt)}.xlsx`;
}

export async function downloadExcelXlsx<Row>(
  filename: string,
  rows: Row[],
  columns: ExportColumn<Row>[],
  options: ExcelReportOptions,
) {
  const { Workbook } = await import("exceljs");
  const generatedAt = new Date();
  const workbook = new Workbook();
  workbook.creator = `${options.organizationName} · ABISSOL V2`;
  workbook.created = generatedAt;
  workbook.modified = generatedAt;
  const footer = options.footer;

  const worksheet = workbook.addWorksheet("Datos", {
    views: [{ state: "frozen", ySplit: 1 }],
    pageSetup: { orientation: "landscape", fitToPage: true, fitToWidth: 1, fitToHeight: 0 },
  });
  worksheet.addRow(columns.map((column) => column.header));
  rows.forEach((row) => worksheet.addRow(columns.map((column) => safeExcelCell(column.value(row)))));

  const thinBorder = {
    top: { style: "thin" as const, color: { argb: "FFD1D5DB" } },
    left: { style: "thin" as const, color: { argb: "FFD1D5DB" } },
    bottom: { style: "thin" as const, color: { argb: "FFD1D5DB" } },
    right: { style: "thin" as const, color: { argb: "FFD1D5DB" } },
  };
  const header = worksheet.getRow(1);
  header.height = 24;
  header.eachCell((cell) => {
    cell.font = { bold: true, color: { argb: "FFFFFFFF" } };
    cell.fill = { type: "pattern", pattern: "solid", fgColor: { argb: "FF15803D" } };
    cell.alignment = { vertical: "middle", horizontal: "center" };
    cell.border = thinBorder;
  });

  rows.forEach((_, rowIndex) => {
    const excelRow = worksheet.getRow(rowIndex + 2);
    excelRow.eachCell({ includeEmpty: true }, (cell, columnIndex) => {
      cell.border = thinBorder;
      cell.alignment = { vertical: "middle", wrapText: true };
      if (rowIndex % 2 === 1) {
        cell.fill = { type: "pattern", pattern: "solid", fgColor: { argb: "FFF0FDF4" } };
      }
      if (typeof cell.value === "number") {
        cell.numFmt = columns[columnIndex - 1]?.numberFormat ?? (Number.isInteger(cell.value) ? "#,##0" : "#,##0.00");
      }
    });
  });

  const dataEndRow = Math.max(1, rows.length + 1);
  worksheet.autoFilter = {
    from: { row: 1, column: 1 },
    to: { row: dataEndRow, column: columns.length },
  };

  if (footer) {
    const footerRow = worksheet.addRow(columns.map((_, index) => safeExcelCell(footer[index])));
    footerRow.height = 22;
    footerRow.eachCell({ includeEmpty: true }, (cell, columnIndex) => {
      cell.font = { bold: true, color: { argb: "FF14532D" } };
      cell.fill = { type: "pattern", pattern: "solid", fgColor: { argb: "FFDCFCE7" } };
      cell.border = thinBorder;
      if (typeof cell.value === "number") {
        cell.numFmt = columns[columnIndex - 1]?.numberFormat ?? (Number.isInteger(cell.value) ? "#,##0" : "#,##0.00");
      }
    });
  }

  columns.forEach((column, index) => {
    const worksheetColumn = worksheet.getColumn(index + 1);
    if (column.width) {
      worksheetColumn.width = column.width;
      return;
    }
    const contentWidth = Math.max(
      column.header.length,
      ...rows.map((row) => String(column.value(row) ?? "").length),
      String(footer?.[index] ?? "").length,
    );
    worksheetColumn.width = Math.min(45, Math.max(12, contentWidth + 2));
  });

  const criteriaSheet = workbook.addWorksheet("Criterios");
  criteriaSheet.addRow(["Institución", safeExcelCell(options.organizationName)]);
  criteriaSheet.addRow(["Generado", `${limaTimestamp(generatedAt).replace("_", " ")} (America/Lima)`]);
  Object.entries(options.criteria).forEach(([label, value]) => criteriaSheet.addRow([label, safeExcelCell(value)]));
  criteriaSheet.getColumn(1).width = 24;
  criteriaSheet.getColumn(2).width = 60;
  criteriaSheet.getColumn(1).font = { bold: true, color: { argb: "FF14532D" } };
  criteriaSheet.eachRow((row) => row.eachCell({ includeEmpty: true }, (cell) => { cell.border = thinBorder; cell.alignment = { vertical: "middle", wrapText: true }; }));

  const buffer = await workbook.xlsx.writeBuffer();
  const blob = new Blob([buffer], {
    type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
  });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = excelFileName(filename, options, generatedAt);
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  window.setTimeout(() => URL.revokeObjectURL(url), 0);
}
