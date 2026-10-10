import { RecordContextMenu } from "@/components/record-context-menu";
import { RowActionsMenu, type RowAction } from "@/components/row-actions-menu";
import { EmissionDelivery } from './emission-delivery';
import { SearchableSelect } from '@/components/searchable-select';
import { useCallback, useEffect, useRef, useState, type FormEvent, type ReactNode } from "react";
import { Download, Plus, RefreshCw, Search, HeartPulse, Users, FileText, Send, Wallet, Receipt, ChartNoAxesCombined, Settings2, Ban, Eye, Pencil, ExternalLink, BookOpen } from "lucide-react";
import axios from "axios";
import api from "@/lib/api";
import { BillingHistory } from "./billing-history";
import { UnderlineTabs } from "@/components/underline-tabs";
import { BillingConfiguration } from "./billing-configuration";
import { BusinessWorkspace, type SectionProps } from "./business-workspace";
import { LiquidationDetail, type SettlementDetail } from "./liquidation-detail";
import { SellerSettlementForm } from "./seller-settlement-form";
import { SellerSettlementDetail } from "./seller-settlement-detail";
import { LiquidationBuilder } from "./business-workspace-panels";
import { EmissionForm } from "./emission-form";
import { useAuth } from "@/context/AuthContext";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/side-dialog";

type Value = string | number | boolean | null;
type Row = Record<string, Value>;
type Option = { value: string; label: string };
type Field = { name: string; label: string; type?: string; options?: Option[]; optional?: boolean; help?: string };
type Lookup = { plans: Row[]; sources: Row[]; profiles: Row[]; users: { id: number; name: string; is_active: boolean; roles: string[] }[]; emissions: Row[]; global_access: boolean; can_configure_billing?: boolean; can_configure_communications?: boolean; test_batch?: string | null; fiscal_enabled?: boolean };
type Listing = { summary?: Record<string, number>; items: Row[]; total: number; count?: number; sales?: string; collected?: string; pending?: string; commissions?: string; provider_cost?: string; unliquidated?: string; expiring?: number };
type Detail = Row & { items?: never; vouchers?: never };
type Modal = { title: string; path: string; method?: "post" | "put"; fields: Field[]; initial?: Row; description?: string };
const empty: Lookup = { plans: [], sources: [], profiles: [], users: [], emissions: [], global_access: false };
const titles: Record<string, string> = { plans: "Planes de asistencia", network: "Red comercial", emissions: "Emisiones", dispatches: "Comunicaciones", liquidations: "Liquidaciones", billing: "Facturación", reports: "Reportes comerciales" };
const icons = { plans: HeartPulse, network: Users, emissions: FileText, dispatches: Send, liquidations: Wallet, billing: Receipt, reports: ChartNoAxesCombined };
const labels: Record<string, string> = { simulated: "Simulado (sin enviar)", test_not_sent: "Prueba (sin SUNAT)", requested: "Solicitada", pending_review: "En revisión", queued: "En cola", uncertain: "Recepción por confirmar", blocked: "Requiere revisión", accepted: "Aceptado por SUNAT", rejected: "Rechazado", error: "Error", generated: "Generado", issued: "Emitido", cancelled: "Anulado", pending: "Pendiente", collected_by_seller: "Cobrado por vendedor", paid_to_abissol: "Ingresado a ABISSOL", settled: "Liquidado", cash: "Efectivo", transfer: "Transferencia", card: "Tarjeta", online: "En línea", source_admin: "Coordinador de origen", responsible: "Vendedor responsable", emitter: "Emisor dependiente", internal: "ABISSOL directo", afocat: "AFOCAT asociada", partner: "Entidad asociada", seller: "Vendedor", meta: "META Assistance", platform: "Plataforma", draft: "Borrador", submitted: "Presentado", approved: "Aprobado", observed: "Observado", paid: "Pagado", email: "Correo", whatsapp: "WhatsApp", sent: "Aceptado por proveedor", failed: "No confirmado", sending: "En curso", not_sent: "Sin enviar", boleta: "Boleta", factura: "Factura" };
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
  const [recordPreview,setRecordPreview]=useState<Row|null>(null);
  const [letterPreview,setLetterPreview]=useState<{url:string;code:string}|null>(null);
  useEffect(() => () => {if(letterPreview) URL.revokeObjectURL(letterPreview.url);}, [letterPreview]);
  const [delivery,setDelivery]=useState<Row|null>(null);
  const [search, setSearch] = useState("");
  const [query, setQuery] = useState("");
  const [emissionState, setEmissionState] = useState("all");
  const [start, setStart] = useState("");
  const [end, setEnd] = useState("");
  const [page, setPage] = useState(0);
  const [modal, setModal] = useState<Modal | null>(null);
  const [detail, setDetail] = useState<SettlementDetail | null>(null);
  const [billingTab, setBillingTab] = useState("documents");
  const [invoiceId, setInvoiceId] = useState<number | null>(null);
  const [busy, setBusy] = useState(false);
  const requestVersion = useRef(0);
  const referencesCache = useRef<Lookup | null>(null);
  const referencesPending = useRef<Promise<Lookup> | null>(null);
  const listingPending = useRef<{key:string;promise:Promise<{data:Listing}>}|null>(null);
  const serverQuery = section === "plans" || section === "network" ? "" : query;
  const editor = !history && can(`medical-${section}`, "editor");
  const manager = !history && can(`medical-${section}`, "gestor");
  const Icon = icons[section as keyof typeof icons] || HeartPulse;
  const load = useCallback(async (refreshReferences = true) => {
    const version = ++requestVersion.current;
    setLoading(true); setError("");
    try {
      const params = { offset: page * 25, limit: 25, kind: liquidationKind, state: section === "emissions" ? emissionState : undefined, search: serverQuery, starts_on: start || undefined, ends_on: end || undefined };
      if (refreshReferences) { referencesCache.current = null; referencesPending.current = null; }
      if (!referencesCache.current && !referencesPending.current) {
        const request = api.get<Lookup>("/medical/lookups", { params: { section } }).then(r => r.data).finally(() => { if (referencesPending.current === request) referencesPending.current = null; });
        referencesPending.current = request;
      }
      const referencesPromise = referencesCache.current ? Promise.resolve(referencesCache.current) : referencesPending.current!;
      const key = JSON.stringify([section,params]);
      if (section !== 'network' && listingPending.current?.key !== key) {
        const promise = api.get<Listing>(`/medical/${section}`, { params }).finally(() => { if (listingPending.current?.promise === promise) listingPending.current = null; });
        listingPending.current = {key,promise};
      }
      const [list, references] = await Promise.all([section === "network" ? referencesPromise.then(refs => ({ data: { items: refs.profiles, total: refs.profiles.length } as Listing })) : listingPending.current!.promise, referencesPromise]);
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
    if (section === "dispatches") setModal({ title: "Enviar constancia", path: "/dispatches", initial: { channel: "email" }, description: lookup.test_batch ? "Las emisiones de prueba registran un envío simulado, sin contactar al destinatario." : "Al confirmar se contactará al destinatario registrado en la emisión. El programador configura los canales en Emisiones / Configuración.", fields: [emissionField, { name: "channel", label: "Canal", options: opts("email", "whatsapp") }] });
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
    try { setDetail((await api.get<SettlementDetail>(`/medical/liquidations/${row.id}`)).data); } catch (e) { setError(errorText(e)); }
  }
  const columns: Record<string, [string, (r: Row) => string][]> = {
    plans: [["Plan", r => `${r.code} · ${r.name}`], ["Precio", r => money(r.price)], ["Proveedor", r => money(r.provider_cost)], ["Vendedor", r => money(r.seller_commission)], ["Vigencia", r => `${r.validity_days} días`], ["Estado", r => r.active ? "Activo" : "Inactivo"]],
    network: [["Participante", r => String(r.display_name || userName(r.user_id))], ["Acceso al portal", r => r.user_id ? userName(r.user_id) : "Sin cuenta ABISSOL"], ["Roles de acceso", r => r.user_id ? (lookup.users.find(u => u.id === Number(r.user_id))?.roles || []).join(", ") || "Sin rol activo" : "Sin acceso al portal"], ["ID externo", r => String(r.external_user_id || "—")], ["Función", r => labels[String(r.kind)]], ["Origen", r => String(lookup.sources.find(s => s.id === r.source_id)?.name || r.source_id)], ["Responsable", r => r.manager_id ? profileName(r.manager_id) : "—"], ["Estado", r => r.active ? "Activo" : "Inactivo"]],
    emissions: [["Certificado", r => String(r.code)], ["Canal / emisor", r => `${r.external_source ? `Externa · ${r.external_source}` : "Interna · ABISSOL"} · ${profileName(r.emitter_id)}`], ["Titular", r => `${r.customer} · ${r.document_number}`], ["Plan", r => String(r.plan_name)], ["Vigencia", r => `${r.starts_on} → ${r.ends_on}`], ["Importe", r => money(r.price)], ["Estado", r => `${labels[String(r.status)]} · ${labels[String(r.payment_status)]}`]],
    dispatches: [["Emisión", r => String(r.invoice_number || r.issuance_code || r.liquidation_code || (r.liquidation_id ? `Liquidación #${r.liquidation_id}` : "Envío general"))], ["Canal", r => labels[String(r.channel)]], ["Destinatario", r => String(r.recipient)], ["Estado", r => labels[String(r.status)] || String(r.status)], ["Intentos", r => String(r.attempts)], ["Detalle", r => String(r.error || "—")]],
    liquidations: [["Número", r => String(r.code || `LIQ-${r.id}`)], ["Tipo", r => labels[String(r.kind)]], ["Responsable", r => profileName(r.responsible_id)], ["Período", r => `${r.starts_on} → ${r.ends_on}`], ["Ventas", r => money(r.sales_total)], ["Comisión / proveedor", r => money(r.commission_total)], ["Depósito", r => money(r.deposit_required)], ["Saldo", r => r.legacy_id ? "Histórico" : money(r.balance_due)], ["Comisión pendiente", r => r.legacy_id || r.kind !== "seller" ? "—" : money(r.commission_due)], ["Estado", r => r.status==="submitted"||r.status==="sent"?"Enviado":r.status==="paid"?"Liquidado":labels[String(r.status)] || String(r.status)]],
    billing: [["Comprobante", r => String(r.full_number || `BOR-${r.id}`)], ["Tipo", r => labels[String(r.document_type)] || String(r.document_type)], ["Cliente", r => String(r.customer)], ["Documento", r => String(r.document_number)], ["Total", r => money(r.total)], ["Estado fiscal", r => `${r.fiscal_environment === "beta" ? "PRUEBA BETA · " : ""}${labels[String(r.sunat_status)] || String(r.sunat_status)}`], ["Estado", r => r.deleted_at ? "Archivado" : labels[String(r.status)] || String(r.status)]],
    reports: [["Plan", r => String(r.plan)], ["Emisiones", r => String(r.count)], ["Ventas", r => money(r.sales)], ["Por cobrar", r => money(r.pending)], ["Por liquidar", r => money(r.unliquidated)], ["Comisiones", r => money(r.commissions)], ["Vencen en 30 días", r => String(r.expiring)]],
  };
  async function exportRows() {
    setBusy(true);
    try {
      const { downloadExcelXlsx } = await import("@/lib/table-tools");
      await downloadExcelXlsx(`abissol-${section}`, data.items, columns[section].map(([header, value]) => ({ header, value })), { organizationName: "ABISSOL", criteria: { Módulo: titles[section], Página: page + 1, Desde: start, Hasta: end } });
    } catch (e) { setError(errorText(e)); } finally { setBusy(false); }
  }
  async function openLetter(r: Row, kind: "letter" | "receipt" | "conditions" = "letter") {
    try {const result=await api.get(kind === "conditions" ? `/medical/validate/${r.token}/conditions` : `/medical/emissions/${r.id}/${kind}`, {responseType:"blob"});setLetterPreview({url:URL.createObjectURL(result.data),code:`${kind === "receipt" ? "Comprobante" : kind === "conditions" ? "Condicionado" : "Carta"} · ${r.code}`});}
    catch(e) {setError(errorText(e));}
  }
  function emissionActions(r: Row): RowAction[] {
    const actions: RowAction[] = [{ label: "Abrir carta PDF", icon: FileText, onSelect: () => void openLetter(r) }];
    actions.push({label: "Ver comprobante", icon: Receipt, onSelect: () => void openLetter(r,"receipt")});
    actions.push({label: "Ver condicionado", icon: BookOpen, onSelect: () => void openLetter(r,"conditions")});
    actions.push({label: "Validar en la web oficial", icon: ExternalLink, onSelect: () => {const token=btoa(JSON.stringify({code:r.token})).replace(/\+/g,"-").replace(/\//g,"_").replace(/=+$/,"");window.open("https://abissol.org/?consulta="+token,"_blank","noopener,noreferrer");}});
    if (r.status === "issued" && can("medical-dispatches", "editor")) actions.push({label: "Enviar al cliente", icon: Send, onSelect: () => setDelivery(r)});
    if (editor && r.status === "issued" && r.payment_status === "pending") actions.push({label: "Registrar cobro", icon: Wallet, onSelect: () => setModal({title: "Confirmar cobro completo", path: `/emissions/${r.id}/payment`, fields: [{name: "payment_status", label: "Destino del dinero", options: opts("collected_by_seller", ...(lookup.global_access ? ["paid_to_abissol"] : []))}, {name: "reference", label: "Referencia del cobro"}], description: `Se registrará el cobro de ${money(r.price)}.`})});
    if (manager && r.status === "issued" && r.payment_status === "pending") actions.push({label: "Anular emisión", icon: Ban, destructive: true, onSelect: () => setModal({title: "Anular emisión", path: `/emissions/${r.id}/cancel`, fields: [reason]})});
    return actions;
  }
  function rowActions(r:Row):RowAction[] {
    if(section === "emissions") return emissionActions(r);
    const actions:RowAction[]=[{label: "Ver detalle",icon:Eye,onSelect:()=>setRecordPreview(r)}];
    if(section === "billing") {
      actions[0]={label:"Historial y archivos",icon:Receipt,onSelect:()=>setInvoiceId(Number(r.id))};
      if(lookup.can_configure_billing && !busy && ['blocked','uncertain'].includes(String(r.sunat_status))) actions.push({label:"Revisar SUNAT",icon:RefreshCw,onSelect:()=>{void (async()=>{setBusy(true);try{await api.post(`/medical/billing/${r.id}/retry`);await load();setNotice('Revisión programada. Si el envío fue incierto, solo se consultará el CDR.');}catch(e){setError(errorText(e));}finally{setBusy(false);}})();}});
      if(editor&&!r.legacy_id&&r.status==="draft") actions.push({label:"Corregir",icon:Pencil,onSelect:()=>invoiceForm(r)});
    }
    if(section==="plans"&&manager)actions.push({label:"Editar",icon:Pencil,onSelect:()=>planForm(r)});
    if(section==="network"&&manager&&lookup.global_access)actions.push({label:"Editar",icon:Pencil,onSelect:()=>profileForm(r)});
    if(section==="dispatches"&&editor&&!r.legacy_id&&!["meta_daily_report","metafin_monthly","invoice_client","settlement_office"].includes(String(r.kind))&&r.status==="failed")actions.push({label:"Reintentar envío",icon:Send,onSelect:()=>setModal({title:"Reintentar envío",path:`/dispatches/${r.id}/retry`,fields:[],description:"Comprueba antes el proveedor: un nuevo envío puede duplicar el mensaje."})});
    if(section==="liquidations") {
      actions[0]={label:"Detalle y conciliación",icon:Eye,onSelect:()=>void showDetail(r)};
      if(r.kind==="meta"&&r.status!=="cancelled") {
        actions.push({label:"Excel META",icon:Download,onSelect:()=>void download(`/liquidations/${r.id}/meta-file/xlsx`,`${r.code||r.id}.xlsx`)},{label:"Carta META",icon:FileText,onSelect:()=>void download(`/liquidations/${r.id}/meta-file/letter`,`carta-${r.code||r.id}.pdf`)});
        if(editor&&lookup.global_access)actions.push({label:"Enviar a META",icon:Send,onSelect:()=>setModal({title:"Enviar altas mensuales a META",path:`/liquidations/${r.id}/meta-send`,fields:[{name:"force",label:"Autorizar reenvío si ya existen intentos previos",type:"checkbox",optional:true}],description:"Se enviará un correo real con el Excel y la carta mensual. Comprueba la recepción antes de autorizar un reenvío."})});
      }
    }
    return actions;
  }
  const visible = section === "plans" || section === "network" ? data.items.filter(r => (JSON.stringify(r) + (section === "network" ? userName(r.user_id) : "")).toLowerCase().includes(query.toLowerCase())) : data.items;
  return <section className={embedded ? "min-w-0 space-y-3" : "space-y-3 p-4 md:p-6"}>
    {lookup.test_batch && <div role="status" className="rounded-xl border border-amber-400 bg-amber-50 p-4 text-sm text-amber-950"><strong>Modo de pruebas activo.</strong> Las nuevas emisiones y comprobantes usan numeración de prueba. SUNAT permanece bloqueado. Correo y WhatsApp solo permiten recepción real en destinatarios de prueba autorizados. Lote: {lookup.test_batch} <a className="ml-2 underline" href="https://app.afocatlaprimera.com/abissol/" target="_blank" rel="noopener noreferrer">Abrir portal oficial de AFOCAT</a></div>}
    <header className="flex flex-wrap items-center justify-between gap-2">{!embedded ? <h1 className="flex items-center gap-2 text-xl font-semibold"><Icon className="size-5 text-emerald-600" />{titles[section]}</h1> : <span className="text-xs text-muted-foreground">{data.total} registros</span>}
      <div className="flex flex-wrap gap-2"><Button size="sm" variant="outline" onClick={() => void load()} disabled={loading}><RefreshCw className="size-4" /> Actualizar</Button>{editor && !(section==="liquidations"&&(liquidationKind||"seller")==="seller") && section !== "reports" && section !== "billing" && (section !== "plans" || manager) && (section !== "network" || (manager && lookup.global_access)) && <Button size="sm" className="bg-emerald-700 text-white hover:bg-emerald-800" onClick={create}><Plus className="size-4" />{section === "network" ? "Nuevo participante" : section === "dispatches" ? "Enviar constancia" : "Nuevo registro"}</Button>}</div>
    </header>
    <UnderlineTabs label={titles[section]} value={lookup.can_configure_billing ? billingTab : "documents"} onChange={setBillingTab} tabs={section === "billing" ? [
      { value: "documents", label: "Comprobantes", icon: <Receipt className="size-4" /> },
      ...(lookup.can_configure_billing ? [{ value: "configuration", label: "Configuración · Programador", icon: <Settings2 className="size-4" /> }] : []),
    ] : []}>
    {section === 'billing' && billingTab === 'configuration' && lookup.can_configure_billing ? <BillingConfiguration updated={load} /> : <>

    {section === "emissions" && data.summary && <div className="flex flex-wrap gap-2" aria-label="Filtrar por vigencia">{[["all","Todas"],["active","Vigentes"],["upcoming","Por iniciar"],["expired","Vencidas"],["cancelled","Anuladas"]].map(([state,label])=><button type="button" key={state} aria-pressed={emissionState===state} onClick={()=>{setEmissionState(state);setPage(0);}} className={`inline-flex items-center gap-2 rounded-lg border px-3 py-2 text-xs ${emissionState===state ? "border-emerald-500 bg-emerald-500/5 text-emerald-700" : "bg-card text-muted-foreground"}`}>{label}<strong className="text-sm tabular-nums">{data.summary?.[state]||0}</strong></button>)}</div>}

    {error && <div role="alert" className="rounded-lg border border-red-300 bg-red-50 p-3 text-sm text-red-800">{error}</div>}
    {notice && <div role="status" className="rounded-lg border border-emerald-300 bg-emerald-50 p-3 text-sm text-emerald-900">{notice}</div>}
    {section==="liquidations"&&(liquidationKind||"seller")==="seller"&&!history&&editor&&<SellerSettlementForm inline profiles={profileOptions("responsible")} close={()=>{}} saved={()=>load(false)}/>}

    {section === "network" && <section className="rounded-xl border bg-card p-4"><div className="mb-3 flex items-center justify-between"><h2 className="font-semibold">Orígenes comerciales</h2>{manager && lookup.global_access && <Button size="sm" variant="outline" onClick={() => sourceForm()}>Agregar origen</Button>}</div><div className="flex flex-wrap gap-2">{lookup.sources.map(s => <button disabled={!manager || !lookup.global_access} key={String(s.id)} onClick={() => sourceForm(s)} className="rounded-lg border px-3 py-2 text-left text-sm disabled:opacity-80">{String(s.name)} <span className="text-muted-foreground">· {labels[String(s.kind)] || s.kind} · {String(s.code)}{!s.active && " · Inactivo"}</span></button>)}{!lookup.sources.length && <p className="text-sm text-muted-foreground">Crea un origen y vincula un responsable para comenzar a emitir.</p>}</div></section>}

    {section === "reports" && <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-7">{[["Emisiones", String(data.count || 0)], ["Ventas", money(data.sales)], ["Recaudado", money(data.collected)], ["Por cobrar", money(data.pending)], ["Comisiones", money(data.commissions)], ["Por liquidar", money(data.unliquidated)], ["Vencen en 30 días", String(data.expiring || 0)]].map(([title, value]) => <div className="rounded-lg border bg-card p-3" key={title}><p className="text-sm text-muted-foreground">{title}</p><p className="mt-1 text-lg font-semibold">{value}</p></div>)}</div>}
    <section className="overflow-hidden rounded-xl border bg-card">
      <div className="flex flex-wrap items-end gap-2 border-b p-3">
        {["plans", "network", "emissions", "billing", "liquidations", "reports"].includes(section) && <form className="flex min-w-52 flex-1 items-end gap-1" onSubmit={e=>{e.preventDefault();setQuery(search);setPage(0);}}><label className="min-w-0 flex-1 text-xs text-muted-foreground">Buscar<Input className="h-9 text-sm" aria-label="Buscar registros" placeholder={section==="emissions"?"Certificado, titular o documento":"Buscar"} value={search} onChange={e=>setSearch(e.target.value)}/></label><Button type="submit" className="size-9" variant="outline" size="icon" aria-label="Buscar"><Search className="size-4"/></Button></form>}
        {["emissions","reports","liquidations","billing"].includes(section) && <><label className="text-xs text-muted-foreground">Desde<Input className="h-9 w-36 text-sm" aria-label="Desde" type="date" value={start} onChange={e=>{setStart(e.target.value);setPage(0);}}/></label><label className="text-xs text-muted-foreground">Hasta<Input className="h-9 w-36 text-sm" aria-label="Hasta" type="date" value={end} onChange={e=>{setEnd(e.target.value);setPage(0);}}/></label></>}
        {(start||end||query||search)&&<Button variant="ghost" size="sm" onClick={()=>{setStart("");setEnd("");setSearch("");setQuery("");setPage(0);}}>Limpiar</Button>}
        <Button className="ml-auto h-9" size="sm" variant="outline" disabled={busy||loading||!data.items.length} onClick={()=>void exportRows()}><Download className="size-4"/>Exportar</Button>
      </div>
      <div className="overflow-x-auto"><table className="w-full text-left text-sm"><thead className="bg-muted/50"><tr>{columns[section].map(([name]) => <th className="whitespace-nowrap px-4 py-3 font-medium" key={name}>{name}</th>)}{section !== "reports" && <th className="px-4 py-3">Acciones</th>}</tr></thead><tbody>{loading ? <tr><td colSpan={columns[section].length + 1} className="p-10 text-center text-muted-foreground">Cargando registros…</td></tr> : !visible.length ? <tr><td colSpan={columns[section].length + 1} className="p-12 text-center text-muted-foreground">No hay registros para mostrar.{editor && section !== "reports" && section !== "billing" ? " Usa la acción superior para comenzar." : ""}</td></tr> : visible.map((r, i) => <MedicalRow key={String(r.id || i)} actions={rowActions(r)}>{columns[section].map(([name, render]) => <td key={name} className="px-4 py-3">{render(r)}</td>)}{section !== "reports" && <td className="w-16 px-4 py-3"><div className="flex flex-wrap gap-2">
        <RowActionsMenu label={String(r.code || r.full_number || r.display_name || r.name || r.id || "registro")} actions={rowActions(r)} />
      </div></td>}</MedicalRow>)}</tbody></table></div>
      <footer className="flex items-center justify-between border-t p-4 text-sm text-muted-foreground"><span>{data.total} registros · {section === "plans" || section === "network" || section === "reports" ? "Listado completo" : `Página ${page + 1}`}</span>{!["plans", "network", "reports"].includes(section) && <div className="flex gap-2"><Button variant="outline" size="sm" disabled={!page || loading} onClick={() => setPage(p => p - 1)}>Anterior</Button><Button variant="outline" size="sm" disabled={(page + 1) * 25 >= data.total || loading} onClick={() => setPage(p => p + 1)}>Siguiente</Button></div>}</footer>
    </section>
    {recordPreview && <Dialog open onOpenChange={open=>{if(!open)setRecordPreview(null);}}><DialogContent><DialogHeader><DialogTitle>{titles[section]} · Detalle</DialogTitle><DialogDescription>Consulta del registro seleccionado.</DialogDescription></DialogHeader><dl className="space-y-4">{columns[section].map(([label,render])=><div key={label}><dt className="text-sm text-muted-foreground">{label}</dt><dd className="break-words font-medium">{render(recordPreview)}</dd></div>)}</dl></DialogContent></Dialog>}
    {letterPreview && <Dialog open onOpenChange={open=>{if(!open)setLetterPreview(null);}}><DialogContent className="sm:max-w-5xl"><DialogHeader><DialogTitle>{letterPreview.code}</DialogTitle><DialogDescription>Documento del programa de asistencia.</DialogDescription></DialogHeader><iframe title="Documento del programa" src={letterPreview.url} className="h-[75vh] w-full rounded-lg border" /></DialogContent></Dialog>}
    {delivery && <EmissionDelivery row={{id:Number(delivery.id),code:String(delivery.code),token:String(delivery.token),email:String(delivery.email||""),phone:String(delivery.phone||""),test_batch:delivery.test_batch?String(delivery.test_batch):null}} close={()=>setDelivery(null)}/>}
    {invoiceId !== null && <BillingHistory key={invoiceId} id={invoiceId} close={() => setInvoiceId(null)} download={download} />}
    {modal?.path === "/liquidations" && (liquidationKind||"seller")!=="seller" && <LiquidationBuilder kind={liquidationKind || "seller"} profiles={profileOptions("responsible")} close={() => setModal(null)} saved={async () => { setModal(null); setNotice("Liquidación generada con las emisiones seleccionadas."); await load(section!=="liquidations"); }} />}
    {modal?.path === "/emissions" && <EmissionForm plans={lookup.plans.filter(p => p.active)} emitters={profileOptions()} globalAccess={lookup.global_access} close={() => setModal(null)} saved={async () => { setModal(null); setNotice("Emisión registrada correctamente."); await load(section!=="liquidations"); }} />}
    {modal && modal.path !== "/emissions" && modal.path !== "/liquidations" && <BusinessForm modal={modal} close={() => setModal(null)} saved={async result => { setModal(null); setNotice(["failed", "uncertain"].includes(String(result.status)) ? "Intento registrado; el proveedor no confirmó el envío. Revisa el detalle." : "Operación registrada correctamente."); await load(section!=="liquidations"); }} />}
    {modal?.path === "/liquidations" && (liquidationKind||"seller")==="seller" && <SellerSettlementForm profiles={profileOptions("responsible")} close={()=>setModal(null)} saved={async()=>{setModal(null);await load(false);}}/>}
    {detail&&detail.kind==="seller"&&!detail.legacy_id&&["submitted","approved","paid"].includes(detail.status)?<SellerSettlementDetail initial={detail} close={()=>setDetail(null)} changed={()=>load(false)} manager={manager&&lookup.global_access}/>:detail&&<LiquidationDetail initial={detail} close={()=>setDetail(null)} changed={()=>load(false)} editor={editor} manager={manager&&lookup.global_access}/>}
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

function MedicalRow({actions, children}: {actions?: RowAction[]; children: ReactNode}) {
  const row = <tr className="border-t hover:bg-muted/30" tabIndex={actions ? 0 : undefined} title={actions ? "Doble clic para abrir · Clic derecho para opciones" : undefined}
    onDoubleClick={event => {if (!(event.target as HTMLElement).closest('button,a,input,[role="menuitem"]')) actions?.[0]?.onSelect();}}
    onKeyDown={event => {if (event.key === "Enter" && event.target === event.currentTarget) {event.preventDefault();actions?.[0]?.onSelect();}}}>{children}</tr>;
  return actions ? <RecordContextMenu actions={actions}>{row}</RecordContextMenu> : row;
}
