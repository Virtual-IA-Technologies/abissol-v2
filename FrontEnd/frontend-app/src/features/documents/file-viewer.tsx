import {lazy, Suspense, useEffect, useRef, useState} from 'react';
import api,{API_ROOT} from '@/lib/api';
import {apiErrorMessage} from '@/lib/api-error';
import {Button} from '@/components/ui/button';
import {Textarea} from '@/components/ui/textarea';
import type {Annotation} from './notes-api';
const Reviewer=lazy(()=>import('./reviewer'));

export function FileViewer({file, documentId, number, notes, onNotes, onDirty, onText, expanded=false}: {
  expanded?: boolean; file: File; documentId?: number; number?: number; notes?: Annotation[];
  onNotes?: (items: Annotation[])=>void; onDirty?: (value: boolean)=>void; onText?: (text: string)=>Promise<void>;
}) {
  const [url,setUrl]=useState('');
  useEffect(()=>{const next=URL.createObjectURL(file);setUrl(next);return()=>URL.revokeObjectURL(next);},[file]);
  const extension=file.name.split('.').pop()?.toLowerCase();
  if(!url)return <p>Cargando vista previa…</p>;
  if(extension==='pdf'||['png','jpg','jpeg','webp'].includes(extension||'')) return <div className={expanded?"h-full min-h-0":"h-[62vh] min-h-80"}><Suspense fallback={<p>Cargando visor…</p>}><Reviewer key={url} fileId={documentId} number={number} url={url} name={file.name} isPdf={extension==='pdf'} localNotes={notes} onLocalNotes={onNotes} onDirtyChange={onDirty}/></Suspense></div>;
  if(['txt','md'].includes(extension||''))return <div className={expanded?'h-full [&>div]:flex [&>div]:h-full [&>div]:flex-col [&_textarea]:min-h-0 [&_textarea]:flex-1 [&_pre]:max-h-none [&_pre]:flex-1 p-2':undefined}><TextViewer file={file} onSave={onText} onDirty={onDirty}/></div>;
  if(['docx','xlsx','pptx'].includes(extension||''))return <OfficePreview file={file}/>;
  return <div className="rounded-lg border p-8 text-center text-sm"><p className="font-medium">{file.name}</p><p className="mt-2 text-muted-foreground">Archivo Office seleccionado. La vista de Microsoft requiere una copia temporal accesible por Internet.</p></div>;
}

function TextViewer({file,onSave,onDirty}:{file: File;onSave?: (text:string)=>Promise<void>;onDirty?: (value:boolean)=>void}) {
  const [text,setText]=useState(''),[original,setOriginal]=useState(''),[busy,setBusy]=useState(false),[error,setError]=useState('');
  useEffect(()=>{let active=true;void file.text().then(s=>{if(active){setText(s);setOriginal(s);}});return()=>{active=false;};},[file]);
  useEffect(()=>{onDirty?.(text!==original);},[text,original,onDirty]);
  return <div className="space-y-3">{onSave?<Textarea aria-label="Contenido del documento" className="h-[55vh] font-mono" maxLength={60000} value={text} onChange={e=>setText(e.target.value)} disabled={busy}/>:<pre className="max-h-[60vh] overflow-auto whitespace-pre-wrap break-words rounded border p-4 text-sm">{text}</pre>}{onSave&&<Button disabled={busy||text===original||!text} onClick={async()=>{setBusy(true);setError('');try{await onSave(text);setOriginal(text);}catch{setError('No se pudo guardar. Conservamos tu texto; revisa si el documento cambió.');}finally{setBusy(false);}}}>{busy?'Guardando…':'Guardar nueva versión'}</Button>}{error&&<p role="alert">{error}</p>}</div>;
}

function DocxViewer({file}:{file:File}) {
  const frame=useRef<HTMLIFrameElement>(null),[error,setError]=useState(''),[loaded,setLoaded]=useState(0);
  useEffect(()=>{if(!loaded)return;let active=true;const show=async()=>{const doc=frame.current?.contentDocument;if(!doc||!active)return;try{const {renderAsync}=await import('docx-preview');if(!active)return;await renderAsync(file,doc.body,undefined,{inWrapper:true,ignoreWidth:true,ignoreHeight:true,renderAltChunks:false});}catch{if(active)setError('No se pudo previsualizar el DOCX. Puedes guardar el archivo original.');}};void show();return()=>{active=false;};},[file,loaded]);
  return <div>{error&&<p role="alert">{error}</p>}<iframe ref={frame} onLoad={()=>setLoaded(value=>value+1)} title={file.name} sandbox="allow-same-origin" className="h-[62vh] w-full border bg-white" srcDoc={'<!doctype html><html><head><meta http-equiv="Content-Security-Policy" content="default-src \'none\'; img-src blob: data:; style-src \'unsafe-inline\'; font-src blob: data:"></head><body></body></html>'}/></div>;
}

function OfficePreview({file}:{file:File}) {
  const [url,setUrl]=useState(''),[busy,setBusy]=useState(false),[error,setError]=useState('');
  const local=['localhost','127.0.0.1'].includes(new URL(API_ROOT).hostname);
  return <div className="space-y-3"><div className="flex flex-wrap items-center gap-3"><Button variant="outline" disabled={busy||local} onClick={async()=>{setBusy(true);setError('');try{const body=new FormData();body.append('file',file);const {data}=await api.post<{token:string}>('/documentos/previas/office',body,{timeout:120000});const source=API_ROOT+'/documentos/publico/archivo?token='+encodeURIComponent(data.token);setUrl('https://view.officeapps.live.com/op/embed.aspx?src='+encodeURIComponent(source));}catch(error){setError(apiErrorMessage(error,'No se pudo preparar la vista de Microsoft'));}finally{setBusy(false);}}}>{busy?'Preparando vista…':url?'Renovar vista Office':'Vista previa Office'}</Button><p className="text-xs text-muted-foreground">{local?'La vista Microsoft requiere abrir ABISSOL desde el servidor.':'Microsoft recibirá una copia temporal de este archivo durante 15 minutos. No se agrega a tu biblioteca.'}</p></div>{error&&<p role="alert" className="text-sm">{error}</p>}{url?<iframe title={file.name} referrerPolicy="no-referrer" src={url} className="h-[62vh] w-full rounded border"/>:file.name.toLowerCase().endsWith('.docx')?<DocxViewer file={file}/>:<p className="rounded border p-8 text-center text-sm">{file.name} · Pulsa Vista previa Office para revisarlo.</p>}</div>;
}
