import type { ReactNode } from 'react';
import { FolderOpen } from 'lucide-react';
import { RecordContextMenu } from './record-context-menu';

export function RecordDrilldown({children,label,onOpen,className}:{children:ReactNode;label:string;onOpen:()=>void;className?:string}){
  return <RecordContextMenu actions={[{label:'Abrir '+label,icon:FolderOpen,onSelect:onOpen}]}><div className={className} tabIndex={0} aria-label={label} title="Doble clic o clic derecho para abrir" onDoubleClick={event=>{if((event.target as Element).closest('button,a,input,textarea,summary,[role="combobox"]'))return;onOpen();}} onKeyDown={event=>{if(event.target===event.currentTarget&&event.key==='Enter'){event.preventDefault();onOpen();}}}>{children}</div></RecordContextMenu>;
}
