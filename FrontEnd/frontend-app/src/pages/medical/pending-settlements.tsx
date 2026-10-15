import { useEffect, useState } from "react";
import api from "@/lib/api";
type Pending = { id: number; code: string; customer: string; sale_date: string; deposit: string; eligible: boolean; test_batch?: string };
const money = (value: number) => new Intl.NumberFormat("es-PE", { style: "currency", currency: "PEN" }).format(value);
export function PendingSettlements({ refreshKey }: { refreshKey: unknown }) {
  const [rows, setRows] = useState<Pending[]>([]);
  const [error, setError] = useState(false);
  const [loading, setLoading] = useState(true);
  useEffect(() => {
    let current = true;
    setLoading(true); setError(false);
    api.get<{ items: Pending[] }>("/medical/seller-pending").then(response => { if (current) setRows(response.data.items.filter(row => row.eligible && !row.test_batch)); }).catch(() => { if (current) setError(true); }).finally(() => { if (current) setLoading(false); });
    return () => { current = false; };
  }, [refreshKey]);
  return <section className="rounded-xl border bg-card p-4"><h2 className="font-semibold">Emisiones pendientes de liquidación</h2><p className="mb-3 text-xs text-muted-foreground">Sin liquidación de vendedor registrada. Los vouchers presentados siguen pendientes de revisión bancaria en el listado superior.</p>{error ? <p role="alert">No se pudieron consultar los pendientes. Actualiza el listado para reintentar.</p> : loading ? <p>Cargando pendientes…</p> : <><div className="overflow-x-auto"><table className="w-full text-left text-sm"><thead><tr>{["Certificado", "Asegurado", "Emisión", "Por depositar"].map(label => <th className="p-2" key={label}>{label}</th>)}</tr></thead><tbody>{rows.map(row => <tr key={row.id}><td className="p-2">{row.code}</td><td className="p-2">{row.customer}</td><td className="p-2">{row.sale_date.split("-").reverse().join("/")}</td><td className="p-2">{money(Number(row.deposit))}</td></tr>)}</tbody><tfoot><tr className="border-t font-semibold"><td className="p-2" colSpan={3}>{rows.length} pendientes · Total</td><td className="p-2">{money(rows.reduce((sum, row) => sum + Number(row.deposit), 0))}</td></tr></tfoot></table></div>{!rows.length && <p className="text-sm text-muted-foreground">No hay emisiones pendientes de presentar.</p>}</>}</section>;
}
