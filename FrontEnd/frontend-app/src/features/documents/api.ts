import api from '@/lib/api';
export interface Folder {id: number; name: string; parent_id: number | null; deleted_at?: string | null}
export interface Version {author_name?: string; id: number; number: number; filename: string; mime: string; size: number; reason: string; created_at: string; processing: string}
export interface DocumentRow {id: number; title: string; description: string; folder_id: number | null; current_version: number; revision: number; owned: boolean; updated_at: string; deleted_at: string | null; file: Version}
export interface Detail extends DocumentRow {versions: Version[]; shares: {id: number; name: string}[]}
export interface DocumentIndex {items: DocumentRow[]; total: number; total_bytes: number}
export interface Filters {q: string; folder?: number; view: string; kind: string; order: string; direction: string; page: number; size: number}
const root='/documentos';
export const documents = {
  copy: (row: DocumentRow, folder_id: number | null) => api.post<DocumentRow>(`${root}/${row.id}/copiar`, {folder_id, revision:row.revision}).then(r=>r.data),
  index: (params: Filters, signal?: AbortSignal) => api.get<DocumentIndex>(root,{params,signal}).then(r=>r.data),
  folders: (trash=false) => api.get<Folder[]>(`${root}/carpetas`,{params:{trash}}).then(r=>r.data),
  folder: (name: string, parent_id: number | null) => api.post(`${root}/carpetas`,{name,parent_id}),
  deleteFolder: (id: number) => api.delete(`${root}/carpetas/${id}`),
  restoreFolder: (id: number) => api.post(`${root}/carpetas/${id}/restaurar`),
  detail: (id: number) => api.get<Detail>(`${root}/${id}`).then(r=>r.data),
  upload: (file: File, folder: number | null, existing?: Detail, reason='Nueva versión') => {
    const body=new FormData(); body.append('file',file);
    if(folder) body.append('folder_id',String(folder));
    if(existing) {body.append('revision',String(existing.revision));body.append('reason',reason);}
    return api.post(root+(existing ? `/${existing.id}/versiones` : ''),body,{timeout:120000});
  },
  update: (row: DocumentRow, title: string, description: string, folder_id: number | null) => api.put<Detail>(`${root}/${row.id}`,{title,description,folder_id,revision:row.revision}).then(r=>r.data),
  share: (row: Detail, recipient: string) => api.post<Detail>(`${root}/${row.id}/compartir`,{recipient,revision:row.revision}).then(r=>r.data),
  unshare: (id: number, share: number) => api.delete(`${root}/${id}/compartir/${share}`),
  trash: (row: DocumentRow) => api.post(`${root}/${row.id}/papelera`,null,{params:{revision:row.revision,restore:!!row.deleted_at}}),
  blob: (id: number, number: number, preview=false) => api.get<Blob>(`${root}/${id}/archivo/${number}`,{responseType:'blob',params:{preview}}).then(r=>r.data),
};
export function saveFile(blob: Blob,name: string) {const url=URL.createObjectURL(blob);const a=document.createElement('a');a.href=url;a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);}
export function sizeLabel(size: number) {return size<1048576 ? `${(size/1024).toFixed(1)} KB` : `${(size/1048576).toFixed(1)} MB`;}
export function dateLabel(value: string) {return new Date(value).toLocaleString('es-PE',{timeZone:'America/Lima',dateStyle:'medium',timeStyle:'short'});}
