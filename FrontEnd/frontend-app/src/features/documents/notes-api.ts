import api from '@/lib/api';
export type Annotation = {id: string; page: number; kind: 'highlight'|'comment'; x: number; y: number; width: number; height: number; text: string};
export type Notes = {items: Annotation[]; revision: number; can_edit: boolean};
export const documentAnnotationAPI = {
  get: (id: number, number: number) => api.get<Notes>(`/documentos/${id}/versiones/${number}/notas`).then(r=>r.data),
  save: (id: number, number: number, revision: number, items: Annotation[]) => api.put<Notes>(`/documentos/${id}/versiones/${number}/notas`, {revision,items}).then(r=>r.data),
};
