import {useEffect,useRef,useState} from 'react';
import api from '@/lib/api';
import {apiErrorMessage} from '@/lib/api-error';
type Editor = {destroyEditor:()=>void};
type OfficeWindow = Window & {DocsAPI?:{DocEditor:new(id:string,config:Record<string,unknown>)=>Editor}};
const scripts = new Map<string,Promise<void>>();
function loadScript(server:string) {
  let pending=scripts.get(server);
  if(!pending){pending=new Promise<void>((resolve,reject)=>{const script=document.createElement('script');script.src=server+'/web-apps/apps/api/documents/api.js';script.onload=()=>resolve();script.onerror=()=>{scripts.delete(server);script.remove();reject(Error('No se pudo conectar con ONLYOFFICE'));};document.head.appendChild(script);});scripts.set(server,pending);}
  return pending;
}
export default function OfficeEditor({id}:{id:number}) {
  const host=useRef<HTMLDivElement>(null),[error,setError]=useState(''),[ready,setReady]=useState(false);
  useEffect(()=>{let active=true;let editor:Editor|undefined;
    void (async()=>{const {data}=await api.post<{server:string;config:Record<string,unknown>}>(`/documentos/office/${id}/config`);await loadScript(data.server);if(!active||!host.current)return;
      const mount=document.createElement('div');mount.id='office-'+crypto.randomUUID();host.current.replaceChildren(mount);
      const Constructor=(window as OfficeWindow).DocsAPI?.DocEditor;if(!Constructor)throw Error('El editor no está disponible');
      editor=new Constructor(mount.id,{...data.config,width:'100%',height:'100%',events:{onAppReady:()=>setReady(true),onError:()=>setError('ONLYOFFICE informó un error. Conserva esta ventana abierta para recuperar tus cambios.')}});
    })().catch(error=>{if(active)setError(apiErrorMessage(error,'No se pudo abrir ONLYOFFICE'));});
    return()=>{active=false;editor?.destroyEditor();};
  },[id]);
  return <div className="relative flex h-full min-h-0 flex-col">{error?<p role="alert" className="shrink-0 border-b p-2 text-sm">{error}</p>:!ready&&<p className="absolute left-3 top-3 text-sm text-muted-foreground">Conectando con el editor…</p>}<div ref={host} className="min-h-0 flex-1"/></div>;
}
