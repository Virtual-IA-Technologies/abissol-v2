import api from "@/lib/api";
export interface Attachment { id: number; articulo_id: number; comentario_id: number | null; nombre: string; mime: string; tamano: number; uso: string }
export interface Article { id: number; titulo: string; resumen: string; categoria: string; audiencia: string; estado: string; origen: string; ruta_fuente: string | null; version: number; actualizado_en: string; contenido?: string; adjuntos?: Attachment[] }
export interface ArticleWrite { titulo: string; resumen: string; categoria: string; audiencia: string; estado: string; contenido: string; motivo: string; version?: number }
export interface CommentAnchor { inicio: number; fin: number }
export interface Annotation { id: number; cita: string; ancla: CommentAnchor | null; version_articulo: number; estado: string }
export interface DocComment extends Annotation { usuario_id: number; autor: string; contenido: string; creado_en: string; adjuntos: Attachment[] }
export interface Revision { id: number; version: number; autor: string; motivo: string; creado_en: string }
export interface RevisionDetail { antes: Partial<Article>; despues: Article; diff: string; campos: string[] }
export interface Index { items: Article[]; total: number; categorias: string[]; puede_editar: boolean }
export type Filters = { q?: string; categoria?: string; audiencia?: string; estado?: string; orden?: string; pagina?: number; tamano?: number };
const root = "/documentacion";
export const docs = {
  index: (params: Filters) => api.get<Index>(root, { params }).then(r => r.data),
  article: (id: number) => api.get<Article>(`${root}/${id}`).then(r => r.data),
  create: (payload: ArticleWrite) => api.post<Article>(root, payload).then(r => r.data),
  update: (id: number, payload: ArticleWrite) => api.put<Article>(`${root}/${id}`, payload).then(r => r.data),
  archive: (id: number, version: number) => api.delete(`${root}/${id}`, { params: { version } }),
  propose: (id: number) => api.post<Article>(`${root}/${id}/propuesta`).then(r => r.data),
  sync: () => api.post<{ actualizados: number }>(`${root}/sincronizar`, {}, { timeout: 120000 }).then(r => r.data),
  comments: (id: number, pagina = 1, q = "") => api.get<{items: DocComment[]; total: number}>(`${root}/${id}/comentarios`, { params: { pagina, q } }).then(r => r.data),
  annotations: (id: number, despues = 0) => api.get<{items: Annotation[]; siguiente: number | null}>(`${root}/${id}/anotaciones`, {params: {despues}}).then(r => r.data),
  commentDetail: (id: number, comment: number) => api.get<DocComment>(`${root}/${id}/comentarios/${comment}`).then(r => r.data),
  comment: (id: number, payload: { contenido: string; cita: string; ancla?: CommentAnchor | null; version_articulo: number; adjuntos: number[] }) => api.post<DocComment>(`${root}/${id}/comentarios`, payload).then(r => r.data),
  moderate: (id: number, comment: number, estado: string) => api.patch(`${root}/${id}/comentarios/${comment}`, {}, { params: { estado } }),
  history: (id: number, pagina = 1) => api.get<{items: Revision[]; total: number}>(`${root}/${id}/revisiones`, { params: { pagina } }).then(r => r.data),
  revision: (id: number, revision: number) => api.get<RevisionDetail>(`${root}/${id}/revisiones/${revision}`).then(r => r.data),
  restore: (id: number, revision: number, version: number, motivo: string) => api.post<Article>(`${root}/${id}/revisiones/${revision}/restaurar`, { version, motivo }).then(r => r.data),
  upload: async (id: number, file: File, uso: "articulo" | "comentario") => {
    const body = new FormData(); body.append("file", await optimizeImage(file)); body.append("uso", uso);
    return (await api.post<Attachment>(`${root}/${id}/adjuntos`, body)).data;
  },
  blob: (path: string) => api.get<Blob>(path, { responseType: "blob" }).then(r => r.data),
  bundle: (params: Filters) => api.get<Blob>(`${root}/paquete`, { params, responseType: "blob" }).then(r => r.data),
  resolve: (id: number, ruta: string) => api.get<{id: number}>(`${root}/resolver`, { params: { desde: id, ruta } }).then(r => r.data),
};
export function saveBlob(blob: Blob, name: string) {
  const url = URL.createObjectURL(blob); const link = document.createElement("a");
  link.href = url; link.download = name; link.click(); setTimeout(() => URL.revokeObjectURL(url), 1000);
}
export const attachmentPath = (a: Attachment) => `${root}/${a.articulo_id}/adjuntos/${a.id}`;
export function errorMessage(error: unknown) {
  const detail = (error as {response?: {data?: {detail?: unknown}}})?.response?.data?.detail;
  return typeof detail === "string" ? detail : "No se pudo completar la operación. Intenta nuevamente.";
}
export const dateLabel = (value: string) => new Date(value).toLocaleString("es-PE", { timeZone: "America/Lima", dateStyle: "medium", timeStyle: "short" });

async function optimizeImage(file: File): Promise<File> {
  if (!/^image\/(png|jpeg|webp)$/.test(file.type) || file.size < 1024 * 1024) return file;
  try {
    const image = await createImageBitmap(file);
    const ratio = Math.min(1, 2048 / Math.max(image.width, image.height));
    const canvas = document.createElement("canvas"); canvas.width = Math.round(image.width * ratio); canvas.height = Math.round(image.height * ratio);
    const context = canvas.getContext("2d"); if (!context) {image.close(); return file;}
    context.drawImage(image, 0, 0, canvas.width, canvas.height); image.close();
    const blob = await new Promise<Blob | null>(resolve => canvas.toBlob(resolve, "image/webp", .9));
    return blob && blob.type === "image/webp" && blob.size < file.size ? new File([blob], file.name.replace(/\.[^.]+$/, "") + ".webp", {type:"image/webp"}) : file;
  } catch { return file; }
}
