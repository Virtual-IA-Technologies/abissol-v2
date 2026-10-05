import { useState } from "react";
import { FileSpreadsheet } from "lucide-react";
import { toast } from "sonner";

import { ActionButton } from "@/components/action-button";

interface ExcelDownloadButtonProps {
  onDownload: () => void | Promise<void>;
  disabled?: boolean;
  label?: string;
}

export function ExcelDownloadButton({
  onDownload,
  disabled = false,
  label = "Descarga Excel",
}: ExcelDownloadButtonProps) {
  const [downloading, setDownloading] = useState(false);

  async function download() {
    try {
      setDownloading(true);
      await onDownload();
    } catch {
      toast.error("No se pudo generar el archivo Excel");
    } finally {
      setDownloading(false);
    }
  }

  return <ActionButton type="button" tone="excel" onClick={download} disabled={disabled || downloading}>
    <FileSpreadsheet className="size-4" />
    {downloading ? "Generando..." : label}
  </ActionButton>;
}
