import { useEffect, useState } from 'react';
import api from '@/lib/api';
import { Button } from '@/components/ui/button';
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from '@/components/ui/dialog';

type Scalar = string | number | boolean | null;
type Detail = {
  id: number; full_number: string; document_type: string; customer: string; total: string; sunat_status: string;
  details: Record<string, unknown> & { items?: Record<string, Scalar>[]; files?: Record<string, number>; unavailable_files?: string[] };
  sunat_logs: Record<string, Scalar>[];
};
type Configuration = Record<string, Scalar | Record<string, Scalar>[]> & { series: Record<string, Scalar>[] };
const money = (value: unknown) => new Intl.NumberFormat('es-PE', { style: 'currency', currency: 'PEN' }).format(Number(value || 0));

export function BillingConfiguration() {
  const [data, setData] = useState<Configuration | null>(null);
  const [error, setError] = useState(false);
  useEffect(() => {
    const controller = new AbortController();
    api.get<Configuration>('/medical/billing/configuration', { signal: controller.signal }).then(r => setData(r.data)).catch(() => { if (!controller.signal.aborted) setError(true); });
    return () => controller.abort();
  }, []);
  if (error) return <p role="alert">No se pudo consultar la configuración fiscal.</p>;
  if (!data?.imported) return null;
  return <details className="rounded-xl border bg-card p-4 text-sm"><summary className="cursor-pointer font-medium">Configuración importada · RUC {String(data.ruc)}</summary><div className="mt-4 space-y-3"><p>{String(data.company_name)} · {String(data.address)}</p><p>Proveedor: {String(data.provider)} · Entorno anterior: {String(data.environment)}. Envío en V2 pendiente de habilitación y validación.</p><p>Credenciales conservadas: {data.credentials_preserved ? 'Sí' : 'No'} · Certificado conservado: {data.certificate_preserved ? 'Sí' : 'No'}</p><div className="flex flex-wrap gap-2">{data.series.map(s => <span className="rounded-lg border p-2" key={String(s.series)}>{String(s.document_type)} · {String(s.series)} · Último número: {String(s.current_number)}</span>)}</div></div></details>;
}

export function BillingHistory({ id, close, download }: { id: number; close: () => void; download: (path: string, filename: string) => Promise<void> }) {
  const [data, setData] = useState<Detail | null>(null);
  const [error, setError] = useState(false);
  useEffect(() => {
    const controller = new AbortController();
    api.get<Detail>(`/medical/billing/${id}/detail`, { signal: controller.signal }).then(r => setData(r.data)).catch(() => { if (!controller.signal.aborted) setError(true); });
    return () => controller.abort();
  }, [id]);
  return <Dialog open onOpenChange={open => { if (!open) close(); }}><DialogContent className="max-h-[85vh] overflow-y-auto sm:max-w-3xl"><DialogHeader><DialogTitle>{data?.full_number || 'Historial del comprobante'}</DialogTitle><DialogDescription>Información y archivos originales de ABISSOL. La consulta no reenvía el comprobante.</DialogDescription></DialogHeader>{error ? <p role="alert">No se pudo cargar el historial.</p> : !data ? <p>Cargando…</p> : <div className="space-y-4"><p>{data.document_type} · {data.customer} · <strong>{money(data.total)}</strong></p><p>Estado SUNAT: {data.sunat_status} · {String(data.details.sunat_message || '')}</p>{Boolean(data.details.affected_series) && <p>Documento afectado: {String(data.details.affected_series)}-{String(data.details.affected_number)} · {String(data.details.credit_note_reason_description || data.details.debit_note_reason_description || '')}</p>}<div className="overflow-x-auto"><table className="w-full text-left text-sm"><thead><tr><th>Descripción</th><th>Cantidad</th><th>Valor</th><th>IGV</th><th>Total</th></tr></thead><tbody>{(data.details.items || []).map((item, index) => <tr className="border-t" key={index}><td className="py-2">{String(item.description)}</td><td>{String(item.quantity)}</td><td>{money(item.subtotal)}</td><td>{money(item.tax_amount)}</td><td>{money(item.total)}</td></tr>)}</tbody></table></div><div className="flex flex-wrap gap-2">{Object.keys(data.details.files || {}).map(kind => <Button key={kind} variant="outline" onClick={() => void download(`/billing/${id}/files/${kind}`, `${data.full_number}-${kind}.${kind === 'PDF' || kind === 'Ticket' ? 'pdf' : kind === 'XML' ? 'xml' : 'zip'}`)}>{kind}</Button>)}</div>{!!data.details.unavailable_files?.length && <p className="text-sm text-amber-800">Archivos ausentes también en el sistema anterior: {data.details.unavailable_files.join(", ")}. Se conserva el registro original.</p>}<h3 className="font-medium">Historial SUNAT</h3>{data.sunat_logs.length ? data.sunat_logs.map((log, index) => <p key={index} className="border-b py-2 text-sm">{String(log.created_at)} · {String(log.action)} · {String(log.status)}{log.error_category ? ` · ${log.error_category}` : ''}</p>) : <p className="text-sm text-muted-foreground">Sin envíos registrados.</p>}</div>}</DialogContent></Dialog>;
}
