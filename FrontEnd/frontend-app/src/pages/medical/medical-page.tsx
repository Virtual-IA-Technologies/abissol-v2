import { SearchableSelect } from '@/components/searchable-select';
import { useCallback, useEffect, useRef, useState, type FormEvent } from "react";
import { Download, Plus, RefreshCw, Search, HeartPulse, Users, FileText, Send, Wallet, Receipt, ChartNoAxesCombined, Settings2 } from "lucide-react";
import axios from "axios";
import api from "@/lib/api";
import { BillingHistory } from "./billing-history";
import { UnderlineTabs } from "@/components/underline-tabs";
import { BillingConfiguration } from "./billing-configuration";
import { BusinessWorkspace, type SectionProps } from "./business-workspace";
import { LiquidationBuilder } from "./business-workspace-panels";
import { EmissionForm } from "./emission-form";
import { useAuth } from "@/context/AuthContext";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";

type Value = string | number | boolean | null;
type Row = Record<string, Value>;
type Option = { value: string; label: string };
type Field = { name: string; label: string; type?: string; options?: Option[]; optional?: boolean; help?: string };
type Lookup = { plans: Row[]; sources: Row[]; profiles: Row[]; users: { id: number; name: string; is_active: boolean; roles: string[] }[]; emissions: Row[]; global_access: boolean; can_configure_billing?: boolean; can_configure_communications?: boolean; fiscal_enabled?: boolean };
type Listing = { summary?: Record<string, number>; items: Row[]; total: number; count?: number; sales?: string; collected?: string; pending?: string; commissions?: string; provider_cost?: string };
type Detail = Row & { items?: never; vouchers?: never };
type LiquidationDetail = { legacy_id?: number | null; items: Row[]; vouchers: Row[]; voucher_total: string; deposit_required: string; status: string };
type Modal = { title: string; path: string; method?: "post" | "put"; fields: Field[]; initial?: Row; description?: string };
const empty: Lookup = { plans: [], sources: [], profiles: [], users: [], emissions: [], global_access: false };
const titles: Record<string, string> = { plans: "Planes de asistencia", network: "Red comercial", emissions: "Emisiones", dispatches: "Comunicaciones", liquidations: "Liquidaciones", billing: "Facturación", reports: "Reportes comerciales" };
const descriptions: Record<string, string> = {
  plans: "Precios, vigencia y comisiones para nuevas emisiones. Las ventas anteriores conservan sus valores.",
  network: "Participantes comerciales, cuentas de acceso y vínculos con AFOCAT independientes.",
  emissions: "Contrata planes, registra cobros y descarga certificados con verificación QR.",
  dispatches: "Envía la constancia por correo o WhatsApp y consulta el resultado de cada intento.",
  liquidations: "Prepara períodos, adjunta depósitos y concilia los ingresos de la red comercial.",
  billing: "Boletas automáticas de emisiones, archivos y seguimiento SUNAT.",
  reports: "Ventas, recaudación y comisiones dentro de tu ámbito comercial.",
};
const icons = { plans: HeartPulse, network: Users, emissions: FileText, dispatches: Send, liquidations: Wallet, billing: Receipt, reports: ChartNoAxesCombined };
const labels: Record<string, string> = { requested: "Solicitada", pending_review: "En revisión", queued: "En cola", uncertain: "Recepción por confirmar", blocked: "Requiere revisión", accepted: "Aceptado por SUNAT", rejected: "Rechazado", error: "Error", generated: "Generado", issued: "Emitido", cancelled: "Anulado", pending: "Pendiente", collected_by_seller: "Cobrado por vendedor", paid_to_abissol: "Ingresado a ABISSOL", settled: "Liquidado", cash: "Efectivo", transfer: "Transferencia", card: "Tarjeta", online: "En línea", source_admin: "Coordinador de origen", responsible: "Vendedor responsable", emitter: "Emisor dependiente", internal: "ABISSOL directo", afocat: "AFOCAT asociada", partner: "Entidad asociada", seller: "Vendedor", meta: "META Assistance", platform: "Plataforma", draft: "Borrador", submitted: "Presentado", approved: "Aprobado", observed: "Observado", paid: "Pagado", email: "Correo", whatsapp: "WhatsApp", sent: "Aceptado por proveedor", failed: "No confirmado", sending: "En curso", not_sent: "Sin enviar", boleta: "Boleta", factura: "Factura" };
const money = (v: Value | undefined) => new Intl.NumberFormat("es-PE", { style: "currency", currency: "PEN" }).format(Number(v || 0));
const opts = (...values: string[]): Option[] => values.map(value => ({ value, label: labels[value] || value }));
function errorText(error: unknown) {
  if (!axios.isAxiosError(error)) return "No se pudo completar la operación";
  const detail = error.response?.data?.detail;
  if (Array.isArray(detail)) return detail.map(e => `${e.loc?.slice(1).join(".")}: ${e.msg}`).join(" · ");
  return typeof detail === "string" ? detail : "No se pudo conectar con el servicio";
}

export default function MedicalPage({ section }: { section: string }) {
  const { user } = useAuth();
  return section === "emissions" || section === "liquidations" ? <BusinessWorkspace key={`${section}-${user?.id}`} section={section} renderSection={props => <MedicalSection key={`${props.section}-${props.liquidationKind || 'history'}`} {...props} />} /> : <MedicalSection key={`${section}-${user?.id}`} section={section} />;
}

function MedicalSection({ section, embedded = false, liquidationKind, history = false }: SectionProps) {
  const { can } = useAuth();
  const [data, setData] = useState<Listing>({ items: [], total: 0 });
  const [lookup, setLookup] = useState<Lookup>(empty);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [search, setSearch] = useState("");
  const [query, setQuery] = useState("");
  const [emissionState, setEmissionState] = useState("all");
  const [start, setStart] = useState("");
  const [end, setEnd] = useState("");
  const [page, setPage] = useState(0);
  const [modal, setModal] = useState<Modal | null>(null);
  const [detail, setDetail] = useState<LiquidationDetail | null>(null);
  const [billingTab, setBillingTab] = useState("documents");
  const [invoiceId, setInvoiceId] = useState<number | null>(null);
  const [busy, setBusy] = useState(false);
  const requestVersion = useRef(0);
  const referencesCache = useRef<Lookup | null>(null);
  const serverQuery = section === "plans" || section === "network" ? "" : query;
  const editor = !history && can(`medical-${section}`, "editor");
  const manager = !history && can(`medical-${section}`, "gestor");
  const Icon = icons[section as keyof typeof icons] || HeartPulse;
  const load = useCallback(async (refreshReferences = true) => {
    const version = ++requestVersion.current;
    setLoading(true); setError("");
    try {
      const params = { offset: page * 25, limit: 25, kind: liquidationKind, state: section === "emissions" ? emissionState : undefined, search: serverQuery, starts_on: start || undefined, ends_on: end || undefined };
      if (refreshReferences) referencesCache.current = null;
      const referencesPromise = referencesCache.current ? Promise.resolve(referencesCache.current) : api.get<Lookup>("/medical/lookups", { params: { section } }).then(r => r.data);
      const [list, references] = await Promise.all([section === "network" ? referencesPromise.then(refs => ({ data: { items: refs.profiles, total: refs.profiles.length } as Listing })) : api.get<Listing>(`/medical/${section}`, { params }), referencesPromise]);
      if (version === requestVersion.current) { referencesCache.current = references; setData(list.data); setLookup(references); }

    } catch (e) { if (version === requestVersion.current) setError(errorText(e)); }
    finally { if (version === requestVersion.current) setLoading(false); }
    }, [section, page, serverQuery, start, end, liquidationKind, emissionState]);
  useEffect(() => { void load(false); }, [load]);
  const userName = (id: Value) => { const account = lookup.users.find(u => u.id === Number(id)); return account ? `${account.name}${account.is_active ? "" : " · Cuenta desactivada"}` : `Usuario ${id}`; };
  const profileName = (id: Value) => { if (!id) return "Consolidado general"; const p = lookup.profiles.find(p => p.id === Number(id)); return p ? String(p.display_name || userName(p.user_id)) : `Perfil ${id}`; };
  const sourceOptions = lookup.sources.filter(p => p.active).map(p => ({ value: String(p.id), label: String(p.name) }));
  const profileOptions = (kind?: string) => lookup.profiles.filter(p => p.active && (section !== "emissions" || p.user_id) && (kind ? p.kind === kind : p.kind !== "source_admin")).map(p => ({ value: String(p.id), label: `${p.display_name || userName(p.user_id)} · ${labels[String(p.kind)]}` }));
  const emissionField: Field = { name: "issuance_id", label: "Emisión", options: lookup.emissions.map(e => ({ value: String(e.id), label: `${e.code} · ${e.customer}` })), help: "Busca por certificado, titular o documento dentro de tu ámbito." };
  const reason: Field = { name: "reason", label: "Motivo / detalle", type: "textarea", help: "Se conservará en auditoría (mínimo cinco caracteres)." };
  function planForm(row?: Row) {
    setModal({ title: row ? "Editar plan" : "Nuevo plan", path: `/plans${row ? `/${row.id}` : ""}`, method: row ? "put" : "post", initial: row || { price: "55.00", provider_cost: "12.00", seller_commission: "15.00", platform_fee: "0.00", meta_percent: "10.00", validity_days: 365, active: true }, fields: [
      { name: "code", label: "Código (mayúsculas)" }, { name: "name", label: "Nombre" }, { name: "prefix", label: "Serie del certificado" },
      { name: "price", label: "Precio S/", type: "money" }, { name: "provider_cost", label: "Costo proveedor S/", type: "money" },
      { name: "seller_commission", label: "Comisión vendedor S/", type: "money" }, { name: "platform_fee", label: "Comisión plataforma S/", type: "money" }, { name: "meta_percent", label: "Comisión META sobre costo (%)", type: "money" },
      { name: "validity_days", label: "Vigencia en días", type: "number" }, { name: "conditions_url", label: "Enlace HTTPS del condicionado", type: "url", optional: true }, { name: "active", label: "Plan activo", type: "checkbox" },
    ] });
  }
  function sourceForm(row?: Row) {
    setModal({ title: row ? "Editar origen" : "Nuevo origen", path: `/sources${row ? `/${row.id}` : ""}`, method: row ? "put" : "post", initial: row || { active: true, kind: "afocat" }, fields: [
      { name: "code", label: "Código (mayúsculas)" }, { name: "name", label: "Nombre de la entidad" },
      { name: "kind", label: "Tipo de origen", options: opts("internal", "afocat", "partner") },
      { name: "external_key", label: "Identificador de integración", optional: true, help: "Ejemplo: externa_alp. Solo para entidades externas; no es una contraseña." },
      { name: "active", label: "Origen activo", type: "checkbox" },
    ] });
  }
  function profileForm(row?: Row) {
    setModal({ title: row ? "Editar participante" : "Nuevo participante", path: `/profiles${row ? `/${row.id}` : ""}`, method: row ? "put" : "post", initial: row || { kind: "responsible", active: true, apply_role: false }, description: "La cuenta permite entrar al portal; el perfil define a quién representa y qué ventas puede consultar. Un participante externo puede existir sin cuenta ABISSOL.", fields: [
      { name: "display_name", label: "Nombre de la persona o punto de venta", optional: true, help: "Obligatorio si no vinculas una cuenta." },
      { name: "source_id", label: "Origen / entidad", options: sourceOptions },
      { name: "kind", label: "Función comercial", options: opts("source_admin", "responsible", "emitter") },
      { name: "manager_id", label: "Vendedor responsable (solo emisores)", options: profileOptions("responsible"), optional: true },
      { name: "external_user_id", label: "ID en la plataforma externa", optional: true, help: "El ID pertenece a la entidad de origen, no a la tabla de usuarios ABISSOL." },
      { name: "user_id", label: "Cuenta de acceso ABISSOL (opcional para externos)", options: lookup.users.map(u => ({ value: String(u.id), label: `${u.name}${u.is_active ? "" : " · Cuenta desactivada"}` })), optional: true },
      { name: "apply_role", label: "Asignar rol comercial recomendado", type: "checkbox", help: "Requiere cuenta. Sustituye solo su rol comercial; conserva roles de plataforma y excepciones individuales." },
      { name: "active", label: "Participante activo", type: "checkbox" },
    ] });
  }
  function create() {
    if (section === "plans") return planForm();
    if (section === "network") return profileForm();
    if (section === "emissions") return setModal({ title: "Nueva emisión", path: "/emissions", fields: [] });
    if (section === "liquidations") return setModal({ title: "Preparar liquidación", path: "/liquidations", fields: [] });
    if (section === "billing") return invoiceForm();
    if (section === "dispatches") setModal({ title: "Enviar constancia", path: "/dispatches", initial: { channel: "email" }, description: "Al confirmar se contactará al destinatario registrado en la emisión. El programador configura los canales en Emisiones / Configuración.", fields: [emissionField, { name: "channel", label: "Canal", options: opts("email", "whatsapp") }] });
  }
  function invoiceForm(row?: Row) {
    setModal({ title: row ? "Corregir borrador" : "Preparar comprobante", path: `/billing${row ? `/${row.id}` : ""}`, method: row ? "put" : "post", initial: row || { document_type: "boleta" }, description: "Este registro es un borrador interno. No asigna serie fiscal ni se envía a SUNAT.", fields: [emissionField, { name: "document_type", label: "Comprobante", options: opts("boleta", "factura") }, { name: "customer", label: "Titular / razón social" }, { name: "document_number", label: "Documento del cliente (RUC para factura)" }] });
  }
  async function download(path: string, filename: string) {
    setError("");
    try { const r = await api.get(`/medical${path}`, { responseType: "blob" }); const url = URL.createObjectURL(r.data); const a = document.createElement("a"); a.href = url; a.download = filename; a.click(); setTimeout(() => URL.revokeObjectURL(url), 1000); }
    catch (e) { setError(errorText(e)); }
  }
  async function showDetail(row: Row) {
    try { setDetail((await api.get<LiquidationDetail>(`/medical/liquidations/${row.id}`)).data); } catch (e) { setError(errorText(e)); }
  }
  const action = (row: Row, name: string, title: string) => setModal({ title, path: `/liquidations/${row.id}/${name}`, fields: [reason], description: "Esta acción modifica el estado de la liquidación y queda registrada en auditoría." });
  const columns: Record<string, [string, (r: Row) => string][]> = {
    plans: [["Plan", r => `${r.code} · ${r.name}`], ["Precio", r => money(r.price)], ["Proveedor", r => money(r.provider_cost)], ["Vendedor", r => money(r.seller_commission)], ["Vigencia", r => `${r.validity_days} días`], ["Estado", r => r.active ? "Activo" : "Inactivo"]],
    network: [["Participante", r => String(r.display_name || userName(r.user_id))], ["Acceso al portal", r => r.user_id ? userName(r.user_id) : "Sin cuenta ABISSOL"], ["Roles de acceso", r => r.user_id ? (lookup.users.find(u => u.id === Number(r.user_id))?.roles || []).join(", ") || "Sin rol activo" : "Sin acceso al portal"], ["ID externo", r => String(r.external_user_id || "—")], ["Función", r => labels[String(r.kind)]], ["Origen", r => String(lookup.sources.find(s => s.id === r.source_id)?.name || r.source_id)], ["Responsable", r => r.manager_id ? profileName(r.manager_id) : "—"], ["Estado", r => r.active ? "Activo" : "Inactivo"]],
    emissions: [["Certificado", r => String(r.code)], ["Canal / emisor", r => `${r.external_source ? `Externa · ${r.external_source}` : "Interna · ABISSOL"} · ${profileName(r.emitter_id)}`], ["Titular", r => `${r.customer} · ${r.document_number}`], ["Plan", r => String(r.plan_name)], ["Vigencia", r => `${r.starts_on} → ${r.ends_on}`], ["Importe", r => money(r.price)], ["Estado", r => `${labels[String(r.status)]} · ${labels[String(r.payment_status)]}`]],
    dispatches: [["Emisión", r => String(r.issuance_code || r.liquidation_code || (r.liquidation_id ? `Liquidación #${r.liquidation_id}` : "Envío general"))], ["Canal", r => labels[String(r.channel)]], ["Destinatario", r => String(r.recipient)], ["Estado", r => labels[String(r.status)] || String(r.status)], ["Intentos", r => String(r.attempts)], ["Detalle", r => String(r.error || "—")]],
    liquidations: [["Número", r => String(r.code || `LIQ-${r.id}`)], ["Tipo", r => labels[String(r.kind)]], ["Responsable", r => profileName(r.responsible_id)], ["Período", r => `${r.starts_on} → ${r.ends_on}`], ["Ventas", r => money(r.sales_total)], ["Comisión / proveedor", r => money(r.commission_total)], ["Depósito", r => money(r.deposit_required)], ["Estado", r => labels[String(r.status)] || String(r.status)]],
    billing: [["Comprobante", r => String(r.full_number || `BOR-${r.id}`)], ["Tipo", r => labels[String(r.document_type)] || String(r.document_type)], ["Cliente", r => String(r.customer)], ["Documento", r => String(r.document_number)], ["Total", r => money(r.total)], ["Estado fiscal", r => `${r.fiscal_environment === "beta" ? "PRUEBA BETA · " : ""}${labels[String(r.sunat_status)] || String(r.sunat_status)}`], ["Estado", r => r.deleted_at ? "Archivado" : labels[String(r.status)] || String(r.status)]],
    reports: [["Plan", r => String(r.plan)], ["Emisiones", r => String(r.count)], ["Ventas", r => money(r.sales)]],
  };
  async function exportRows() {
    setBusy(true);
    try {
      const { downloadExcelXlsx } = await import("@/lib/table-tools");
      await downloadExcelXlsx(`abissol-${section}`, data.items, columns[section].map(([header, value]) => ({ header, value })), { organizationName: "ABISSOL", criteria: { Módulo: titles[section], Página: page + 1, Desde: start, Hasta: end } });
    } catch (e) { setError(errorText(e)); } finally { setBusy(false); }
  }
  const visible = section === "plans" || section === "network" ? data.items.filter(r => (JSON.stringify(r) + (section === "network" ? userName(r.user_id) : "")).toLowerCase().includes(query.toLowerCase())) : data.items;
  return <section className={embedded ? "min-w-0 space-y-6" : "space-y-6 p-4 md:p-6"}>
    <header className="flex flex-wrap items-start justify-between gap-4"><div className="flex gap-3"><span className="rounded-xl bg-emerald-500/10 p-3 text-emerald-600"><Icon className="size-6" /></span><div><p className="text-xs font-medium uppercase tracking-widest text-emerald-600">Negocio ABISSOL</p><h1 className="text-2xl font-semibold">{section === "liquidations" ? (history ? "Historial de liquidaciones" : liquidationKind === "meta" ? "Liquidaciones mensuales META" : liquidationKind === "platform" ? "Liquidación de plataforma" : "Liquidaciones de vendedores") : titles[section]}</h1><p className="mt-1 max-w-2xl text-sm text-muted-foreground">{descriptions[section]}</p></div></div>
      <div className="flex flex-wrap gap-2"><Button variant="outline" onClick={() => void load()} disabled={loading}><RefreshCw className="size-4" /> Actualizar</Button>{editor && section !== "reports" && section !== "billing" && (section !== "plans" || manager) && (section !== "network" || (manager && lookup.global_access)) && <Button className="bg-emerald-700 text-white hover:bg-emerald-800" onClick={create}><Plus className="size-4" />{section === "network" ? "Nuevo participante" : section === "dispatches" ? "Enviar constancia" : "Nuevo registro"}</Button>}</div>
    </header>
    <UnderlineTabs label={titles[section]} value={lookup.can_configure_billing ? billingTab : "documents"} onChange={setBillingTab} tabs={section === "billing" ? [
      { value: "documents", label: "Comprobantes", icon: <Receipt className="size-4" /> },
      ...(lookup.can_configure_billing ? [{ value: "configuration", label: "Configuración · Programador", icon: <Settings2 className="size-4" /> }] : []),
    ] : []}>
    {section === 'billing' && billingTab === 'configuration' && lookup.can_configure_billing ? <BillingConfiguration updated={load} /> : <>
    {section === 'billing' && <div className="rounded-xl border bg-emerald-500/5 p-4 text-sm">{lookup.fiscal_enabled ? 'La boleta se genera y envía automáticamente al registrar una emisión. El cobro se confirma por separado. Consulta aquí su PDF, XML y CDR.' : 'La emisión automática espera la activación de la configuración fiscal por el programador.'}</div>}
    {section === "emissions" && data.summary && <section className="space-y-3"><div><h2 className="font-semibold">Resumen de afiliaciones</h2><p className="text-sm text-muted-foreground">Indicadores del período y búsqueda. Selecciona una tarjeta para filtrar.</p></div><div className="grid grid-cols-2 gap-3 lg:grid-cols-5">{[["all","Todas"],["active","Vigentes"],["upcoming","Por iniciar"],["expired","Vencidas"],["cancelled","Anuladas"]].map(([state,label])=><button type="button" key={state} aria-pressed={emissionState===state} onClick={()=>{setEmissionState(state);setPage(0);}} className={`rounded-xl border p-4 text-left ${emissionState===state ? "border-emerald-500 bg-emerald-500/5" : "bg-card"}`}><span className="text-sm text-muted-foreground">{label}</span><strong className="mt-1 block text-2xl">{data.summary?.[state]||0}</strong></button>)}</div></section>}
    {error && <div role="alert" className="rounded-lg border border-red-300 bg-red-50 p-3 text-sm text-red-800">{error}</div>}
    {notice && <div role="status" className="rounded-lg border border-emerald-300 bg-emerald-50 p-3 text-sm text-emerald-900">{notice}</div>}
    {section === "network" && <div className="grid gap-3 md:grid-cols-3">{[["Vendedor responsable", "Puede emitir y consultar sus ventas y las de sus emisores. Prepara sus liquidaciones."], ["Emisor dependiente", "Registra y consulta sus propias emisiones. La comisión y liquidación corresponden a su responsable."], ["Coordinador de origen", "Consulta la operación de su entidad y prepara sus liquidaciones. No administra la plataforma ni aprueba pagos."]].map(([title, text]) => <div key={title} className="rounded-xl border bg-card p-4"><h2 className="font-medium">{title}</h2><p className="mt-2 text-sm text-muted-foreground">{text}</p></div>)}</div>}
    {section === "network" && <section className="rounded-xl border bg-card p-4"><div className="mb-3 flex items-center justify-between"><h2 className="font-semibold">Orígenes comerciales</h2>{manager && lookup.global_access && <Button size="sm" variant="outline" onClick={() => sourceForm()}>Agregar origen</Button>}</div><div className="flex flex-wrap gap-2">{lookup.sources.map(s => <button disabled={!manager || !lookup.global_access} key={String(s.id)} onClick={() => sourceForm(s)} className="rounded-lg border px-3 py-2 text-left text-sm disabled:opacity-80">{String(s.name)} <span className="text-muted-foreground">· {labels[String(s.kind)] || s.kind} · {String(s.code)}{!s.active && " · Inactivo"}</span></button>)}{!lookup.sources.length && <p className="text-sm text-muted-foreground">Crea un origen y vincula un responsable para comenzar a emitir.</p>}</div></section>}
    {(section === "emissions" || section === "reports" || section === "liquidations") && <div className="flex flex-wrap items-end gap-3"><label className="text-sm">Desde<Input aria-label="Desde" type="date" value={start} onChange={e => { setStart(e.target.value); setPage(0); }} /></label><label className="text-sm">Hasta<Input aria-label="Hasta" type="date" value={end} onChange={e => { setEnd(e.target.value); setPage(0); }} /></label></div>}
    {section === "reports" && <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-5">{[["Emisiones", String(data.count || 0)], ["Ventas", money(data.sales)], ["Recaudado", money(data.collected)], ["Por cobrar", money(data.pending)], ["Comisiones", money(data.commissions)]].map(([title, value]) => <div className="rounded-xl border bg-card p-5" key={title}><p className="text-sm text-muted-foreground">{title}</p><p className="mt-2 text-2xl font-semibold">{value}</p></div>)}</div>}
    <section className="overflow-hidden rounded-xl border bg-card">
      <div className="flex flex-wrap items-center justify-between gap-3 border-b p-4">{["plans", "network", "emissions"].includes(section) ? <form className="flex gap-2" onSubmit={e => { e.preventDefault(); setQuery(search); setPage(0); }}><Input aria-label="Buscar registros" placeholder={section === "emissions" ? "Certificado, titular o documento" : "Buscar"} value={search} onChange={e => setSearch(e.target.value)} /><Button type="submit" variant="outline" size="icon" aria-label="Buscar"><Search className="size-4" /></Button></form> : <span className="text-sm text-muted-foreground">{data.total} registros</span>}<Button variant="outline" disabled={busy || loading || !data.items.length} onClick={() => void exportRows()}><Download className="size-4" /> Exportar página</Button></div>
      <div className="overflow-x-auto"><table className="w-full text-left text-sm"><thead className="bg-muted/50"><tr>{columns[section].map(([name]) => <th className="whitespace-nowrap px-4 py-3 font-medium" key={name}>{name}</th>)}{section !== "reports" && <th className="px-4 py-3">Acciones</th>}</tr></thead><tbody>{loading ? <tr><td colSpan={columns[section].length + 1} className="p-10 text-center text-muted-foreground">Cargando registros…</td></tr> : !visible.length ? <tr><td colSpan={columns[section].length + 1} className="p-12 text-center text-muted-foreground">No hay registros para mostrar.{editor && section !== "reports" && section !== "billing" ? " Usa la acción superior para comenzar." : ""}</td></tr> : visible.map((r, i) => <tr key={String(r.id || i)} className="border-t hover:bg-muted/30">{columns[section].map(([name, render]) => <td key={name} className="px-4 py-3">{render(r)}</td>)}{section !== "reports" && <td className="min-w-44 px-4 py-3"><div className="flex flex-wrap gap-2">
        {section === "plans" && manager && <Button size="sm" variant="outline" onClick={() => planForm(r)}>Editar</Button>}
        {section === "network" && manager && lookup.global_access && <Button size="sm" variant="outline" onClick={() => profileForm(r)}>Editar</Button>}
        {section === "emissions" && <><Button size="sm" variant="outline" onClick={() => void download(`/emissions/${r.id}/letter`, `${r.code}.pdf`)}>Carta PDF</Button>{editor && r.status === "issued" && r.payment_status === "pending" && <Button size="sm" variant="outline" onClick={() => setModal({ title: "Confirmar cobro completo", path: `/emissions/${r.id}/payment`, fields: [{ name: "payment_status", label: "Destino del dinero", options: opts("collected_by_seller", ...(lookup.global_access ? ["paid_to_abissol"] : [])) }, { name: "reference", label: "Referencia del cobro" }], description: `Se registrará el cobro de ${money(r.price)}.` })}>Registrar cobro</Button>}{manager && r.status === "issued" && r.payment_status === "pending" && <Button size="sm" variant="outline" onClick={() => setModal({ title: "Anular emisión", path: `/emissions/${r.id}/cancel`, fields: [reason] })}>Anular</Button>}</>}
        {section === "billing" && <Button size="sm" variant="outline" onClick={() => setInvoiceId(Number(r.id))}>Historial y archivos</Button>}
        {section === "billing" && lookup.can_configure_billing && ['blocked','uncertain'].includes(String(r.sunat_status)) && <Button size="sm" variant="outline" disabled={busy} onClick={async()=>{setBusy(true);try{await api.post(`/medical/billing/${r.id}/retry`);await load();setNotice('Revisión programada. Si el envío fue incierto, solo se consultará el CDR.');}catch(e){setError(errorText(e));}finally{setBusy(false);}}}>Revisar SUNAT</Button>}
        {section === "billing" && editor && !r.legacy_id && r.status === "draft" && <Button size="sm" variant="outline" onClick={() => invoiceForm(r)}>Corregir</Button>}
        {section === "dispatches" && editor && !r.legacy_id && !["meta_daily_report", "metafin_monthly"].includes(String(r.kind)) && r.status === "failed" && <Button size="sm" variant="outline" onClick={() => setModal({ title: "Reintentar envío", path: `/dispatches/${r.id}/retry`, fields: [], description: "Comprueba antes el proveedor: si el intento anterior sí llegó, un nuevo envío duplicará el mensaje." })}>Reintentar</Button>}
        {section === "liquidations" && r.kind === "meta" && r.status !== "cancelled" && <><Button size="sm" variant="outline" onClick={() => void download(`/liquidations/${r.id}/meta-file/xlsx`, `${r.code || r.id}.xlsx`)}>Excel META</Button><Button size="sm" variant="outline" onClick={() => void download(`/liquidations/${r.id}/meta-file/letter`, `carta-${r.code || r.id}.pdf`)}>Carta META</Button>{editor && lookup.global_access && <Button size="sm" variant="outline" onClick={() => setModal({title:"Enviar altas mensuales a META",path:`/liquidations/${r.id}/meta-send`,fields:[{name:"force",label:"Autorizar reenvío si ya existen intentos previos",type:"checkbox",optional:true}],description:"Se enviará un correo real al destinatario META configurado, con el Excel de altas y la carta mensual. Comprueba la recepción antes de autorizar un reenvío."})}>Enviar a META</Button>}</>}
        {section === "liquidations" && <><Button size="sm" variant="outline" onClick={() => void showDetail(r)}>Detalle</Button>{editor && r.kind !== "meta" && ["draft", "observed"].includes(String(r.status)) && <><Button size="sm" variant="outline" onClick={() => setModal({ title: "Adjuntar comprobante", path: `/liquidations/${r.id}/vouchers`, fields: [{ name: "reference", label: "Referencia bancaria única" }, { name: "amount", label: "Importe S/", type: "money" }, { name: "paid_on", label: "Fecha del depósito", type: "date" }, { name: "file", label: "PDF, PNG o JPEG (máximo 5 MB)", type: "file" }] })}>Comprobante</Button><Button size="sm" variant="outline" onClick={() => action(r, "submit", "Presentar liquidación")}>Presentar</Button><Button size="sm" variant="outline" onClick={() => action(r, "cancel", "Cancelar liquidación")}>Cancelar</Button></>}{manager && r.kind !== "meta" && lookup.global_access && r.status === "submitted" && <><Button size="sm" onClick={() => action(r, "approve", "Aprobar conciliación")}>Aprobar</Button><Button size="sm" variant="outline" onClick={() => action(r, "observe", "Observar liquidación")}>Observar</Button></>}{manager && r.kind !== "meta" && lookup.global_access && r.status === "approved" && <Button size="sm" onClick={() => action(r, "pay", "Confirmar cierre y pago")}>Cerrar y pagar</Button>}</>}
      </div></td>}</tr>)}</tbody></table></div>
      <footer className="flex items-center justify-between border-t p-4 text-sm text-muted-foreground"><span>{data.total} registros · {section === "plans" || section === "network" || section === "reports" ? "Listado completo" : `Página ${page + 1}`}</span>{!["plans", "network", "reports"].includes(section) && <div className="flex gap-2"><Button variant="outline" size="sm" disabled={!page || loading} onClick={() => setPage(p => p - 1)}>Anterior</Button><Button variant="outline" size="sm" disabled={(page + 1) * 25 >= data.total || loading} onClick={() => setPage(p => p + 1)}>Siguiente</Button></div>}</footer>
    </section>
    {invoiceId !== null && <BillingHistory key={invoiceId} id={invoiceId} close={() => setInvoiceId(null)} download={download} />}
    {modal?.path === "/liquidations" && <LiquidationBuilder kind={liquidationKind || "seller"} profiles={profileOptions("responsible")} close={() => setModal(null)} saved={async () => { setModal(null); setNotice("Liquidación generada con las emisiones seleccionadas."); await load(); }} />}
    {modal?.path === "/emissions" && <EmissionForm plans={lookup.plans.filter(p => p.active)} emitters={profileOptions()} globalAccess={lookup.global_access} close={() => setModal(null)} saved={async () => { setModal(null); setNotice("Emisión registrada correctamente."); await load(); }} />}
    {modal && modal.path !== "/emissions" && modal.path !== "/liquidations" && <BusinessForm modal={modal} close={() => setModal(null)} saved={async result => { setModal(null); setNotice(["failed", "uncertain"].includes(String(result.status)) ? "Intento registrado; el proveedor no confirmó el envío. Revisa el detalle." : "Operación registrada correctamente."); await load(); }} />}
    <Dialog open={!!detail} onOpenChange={open => { if (!open) setDetail(null); }}><DialogContent className="max-h-[85vh] overflow-y-auto sm:max-w-2xl"><DialogHeader><DialogTitle>Detalle de liquidación</DialogTitle><DialogDescription>{detail?.legacy_id ? "Liquidación importada: consulta de la conciliación original, sin modificar sus estados históricos." : "Importes conservados al preparar el período."}</DialogDescription></DialogHeader>{detail && <div className="space-y-4"><p>Depósito requerido: <strong>{money(detail.deposit_required)}</strong> · Adjuntado: <strong>{money(detail.voucher_total)}</strong></p><h3 className="font-medium">Emisiones incluidas</h3>{detail.items.map(i => <div key={String(i.id)} className="flex justify-between border-b py-2 text-sm"><span>{String(i.code || `Emisión #${i.issuance_id}`)} · {String(i.customer || "")}</span><span>Venta {money(i.sale)} · Comisión {money(i.commission)} · Depósito {money(i.deposit)}</span></div>)}<h3 className="font-medium">Comprobantes</h3>{detail.vouchers.length ? detail.vouchers.map(v => <div key={String(v.id)} className="flex flex-wrap gap-2"><Button variant="outline" onClick={() => void download(`/vouchers/${v.id}/file`, String(v.filename))}>{String(v.reference)} · {money(v.amount)} <Download className="size-4" /></Button>{editor && ["draft", "observed"].includes(detail.status) && <Button variant="outline" onClick={() => { setDetail(null); setModal({ title: "Retirar comprobante", path: `/vouchers/${v.id}/void`, fields: [reason], description: "Se conserva el archivo y su auditoría. Podrás adjuntar el comprobante correcto." }); }}>Retirar</Button>}</div>) : <p className="text-sm text-muted-foreground">Sin comprobantes adjuntos.</p>}</div>}</DialogContent></Dialog>
    </>}
    </UnderlineTabs>
  </section>;
}

function BusinessForm({ modal, close, saved }: { modal: Modal; close: () => void; saved: (row: Detail) => Promise<void> }) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setBusy(true); setError("");
    const form = new FormData(event.currentTarget);
    const missing = modal.fields.find(f => !f.optional && (f.options || f.name === "issuance_id") && !form.get(f.name));
    if (missing) { setError(`Selecciona ${missing.label.toLowerCase()}.`); setBusy(false); return; }
    const payload: Record<string, Value> = {};
    modal.fields.forEach(f => {
      const value = String(form.get(f.name) || "").trim();
      payload[f.name] = f.type === "checkbox" ? form.has(f.name) : (f.name === "external_user_id" || f.name === "external_key") ? value || null : f.name.endsWith("_id") ? value ? Number(value) : null : f.type === "number" ? Number(value) : value;
    });
    try {
      const response = await api[modal.method || "post"](`/medical${modal.path}`, modal.fields.some(f => f.type === "file") ? form : payload);
      await saved(response.data);
    } catch (e) { setError(errorText(e)); } finally { setBusy(false); }
  }
  return <Dialog open onOpenChange={open => { if (!open && !busy) close(); }}><DialogContent className="max-h-[90vh] overflow-y-auto sm:max-w-xl"><DialogHeader><DialogTitle>{modal.title}</DialogTitle><DialogDescription>{modal.description || "Completa los datos para guardar la operación."}</DialogDescription></DialogHeader><form onSubmit={submit} className="space-y-4">{error && <p role="alert" className="rounded-lg bg-red-50 p-3 text-sm text-red-800">{error}</p>}<div className="grid gap-4 sm:grid-cols-2">{modal.fields.map(f => <label key={f.name} className={`${f.type === "textarea" ? "sm:col-span-2" : ""} space-y-1 text-sm`}><span className="font-medium">{f.label}</span>{f.name === "issuance_id" ? <EmissionPicker section={modal.path.startsWith("/billing") ? "billing" : "dispatches"} selected={modal.initial?.issuance_id} /> : f.options ? <FormSelect name={f.name} label={f.label} options={f.options} initial={String(modal.initial?.[f.name] || "")} optional={f.optional} disabled={busy} /> : f.type === "checkbox" ? <input className="ml-3 size-4 accent-emerald-700" name={f.name} type="checkbox" defaultChecked={Boolean(modal.initial?.[f.name])} /> : f.type === "textarea" ? <textarea className="min-h-24 w-full rounded-md border bg-background p-3" name={f.name} required minLength={5} maxLength={1000} /> : <Input name={f.name} type={f.type === "money" ? "number" : f.type || "text"} step={f.type === "money" ? "0.01" : undefined} min={f.type === "money" ? 0 : f.type === "number" ? 1 : undefined} required={!f.optional} defaultValue={f.type === "file" ? undefined : String(modal.initial?.[f.name] ?? "")} accept={f.type === "file" ? ".pdf,.png,.jpg,.jpeg" : undefined} />}{f.help && <p className="text-xs text-muted-foreground">{f.help}</p>}</label>)}</div><div className="flex justify-end gap-2 border-t pt-4"><Button type="button" variant="outline" onClick={close} disabled={busy}>Cancelar</Button><Button type="submit" className="bg-emerald-700 text-white hover:bg-emerald-800" disabled={busy}>{busy ? "Procesando…" : (modal.path.includes("dispatches") || modal.path.endsWith("meta-send")) ? "Confirmar envío" : "Guardar"}</Button></div></form></DialogContent></Dialog>;
}


function FormSelect({ name, label, options, initial, optional, disabled }: { name: string; label: string; options: Option[]; initial: string; optional?: boolean; disabled?: boolean }) {
  const [value, setValue] = useState(initial);
  return <><input type="hidden" name={name} value={value} /><SearchableSelect aria-label={label} options={optional ? [{value:'',label:'Sin selección'}, ...options] : options} value={value} onValueChange={setValue} disabled={disabled} /></>;
}

function EmissionPicker({ section, selected }: { section: string; selected?: Value }) {
  const [value, setValue] = useState(String(selected || ""));
  const [search, setSearch] = useState("");
  const [options, setOptions] = useState<Option[]>([]);
  const [error, setError] = useState("");
  useEffect(() => {
    const controller = new AbortController();
    const timer = setTimeout(() => {
      api.get<Option[]>("/medical/issuance-options", { params: { section, search, selected: value || undefined }, signal: controller.signal })
        .then(r => { setOptions(r.data); setError(""); })
        .catch(e => { if (!controller.signal.aborted) setError(errorText(e)); });
    }, 250);
    return () => { clearTimeout(timer); controller.abort(); };
  }, [section, search, value]);
  return <span className="block space-y-2"><input type="hidden" name="issuance_id" value={value} /><SearchableSelect aria-label="Emisión seleccionada" options={options} value={value} onValueChange={setValue} onSearchChange={setSearch} searchPlaceholder="Buscar certificado o titular…" placeholder="Seleccionar emisión" />{error && <span role="alert" className="text-red-700">{error}</span>}</span>;
}
