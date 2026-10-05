import { useEffect, useRef, useState } from "react";
import axios from "axios";
import { LoaderCircle } from "lucide-react";

import { SearchableSelect } from "@/components/searchable-select";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { lookupDocument, type DocumentLookup, type DocumentType } from "@/lib/smart-forms-api";

type Props = {
  optionSlug: string;
  documentType: DocumentType;
  documentNumber: string;
  onDocumentTypeChange: (value: DocumentType) => void;
  onDocumentNumberChange: (value: string) => void;
  onResolved?: (result: DocumentLookup) => void;
  disabled?: boolean;
};

export function SmartDocumentField(props: Props) {
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState("");
  const requestId = useRef(0);
  const onResolved = useRef(props.onResolved);
  onResolved.current = props.onResolved;
  const length = props.documentType === "dni" ? 8 : 11;

  useEffect(() => {
    const currentRequest = ++requestId.current;
    if (props.disabled || props.documentNumber.length !== length) {
      setLoading(false);
      setMessage("");
      return;
    }
    setLoading(true);
    setMessage("Consultando automáticamente...");
    const timer = window.setTimeout(() => {
      void lookupDocument(props.optionSlug, props.documentType, props.documentNumber)
        .then((result) => {
          if (requestId.current !== currentRequest) return;
          onResolved.current?.(result);
          setMessage(result.business_name || result.full_name || "Documento encontrado.");
        })
        .catch((error) => {
          if (requestId.current !== currentRequest) return;
          setMessage(axios.isAxiosError(error) ? error.response?.data?.detail || "No se pudo consultar el documento." : "No se pudo consultar el documento.");
        })
        .finally(() => {
          if (requestId.current === currentRequest) setLoading(false);
        });
    }, 450);
    return () => window.clearTimeout(timer);
  }, [length, props.disabled, props.documentNumber, props.documentType, props.optionSlug]);

  return <div className="space-y-2">
    <Label>Documento</Label>
    <div className="grid grid-cols-[8rem_1fr] gap-2">
      <SearchableSelect value={props.documentType} onValueChange={(value) => { props.onDocumentTypeChange(value as DocumentType); props.onDocumentNumberChange(""); setMessage(""); }} options={[{ value: "dni", label: "DNI" }, { value: "ruc", label: "RUC" }]} disabled={props.disabled} />
      <div className="relative"><Input inputMode="numeric" autoComplete="off" value={props.documentNumber} maxLength={length} placeholder={`${length} dígitos`} disabled={props.disabled} className="pr-9" onChange={(event) => props.onDocumentNumberChange(event.target.value.replace(/\D/g, "").slice(0, length))} />{loading && <LoaderCircle className="absolute right-3 top-3 size-4 animate-spin text-muted-foreground" aria-label="Consultando documento" />}</div>
    </div>
    {message && <p className="text-xs text-muted-foreground" role="status">{message}</p>}
  </div>;
}
