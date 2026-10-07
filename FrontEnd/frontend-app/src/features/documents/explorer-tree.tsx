import { useState, type DragEvent } from 'react';
import { ChevronRight, Folder, FolderOpen, HardDrive, Share2, Trash2 } from 'lucide-react';
import { DriveIcon } from './drive-icon';
import type { Folder as DocumentFolder } from './api';

type Props = {
  folders: DocumentFolder[];
  folder: number | undefined;
  location: string;
  navigate: (id: number | undefined) => void;
  onLocation: (value: string) => void;
  dropProps: (id: number) => {
    onDragOver: (event: DragEvent) => void;
    onDragLeave: () => void;
    onDrop: (event: DragEvent) => void;
    style: { outline: string; background: string } | undefined;
  };
};

export function ExplorerTree({ folders, folder, location, navigate, onLocation, dropProps }: Props) {
  const [expanded, setExpanded] = useState<Record<number, boolean>>({});
  const ancestors = new Set<number>();
  let current = folders.find(item => item.id === folder);
  while (current && !ancestors.has(current.id)) {
    ancestors.add(current.id);
    current = folders.find(item => item.id === current?.parent_id);
  }
  const branch = (parent: number | null, depth = 0, managed=false) => {
    if (depth > 10) return null;
    return folders.filter(item => item.parent_id === parent && !!item.managed===managed)
      .sort((a, b) => a.name.localeCompare(b.name, 'es', { numeric: true }))
      .map(item => {
        const children = folders.some(child => child.parent_id === item.id);
        const opened = expanded[item.id] ?? ancestors.has(item.id);
        const active = folder === item.id;
        const Icon = active ? FolderOpen : Folder;
        return <li key={item.id}>
          <div {...dropProps(item.id)} className={`flex items-center rounded-md ${active ? 'bg-accent text-accent-foreground' : 'hover:bg-muted'}`}>
            <button type="button" className="flex size-7 shrink-0 items-center justify-center" disabled={!children} aria-label={`${opened ? 'Contraer' : 'Expandir'} ${item.name}`} aria-expanded={children ? opened : undefined} onClick={() => setExpanded(old => ({ ...old, [item.id]: !opened }))}>
              {children && <ChevronRight className={`size-3 transition-transform ${opened ? 'rotate-90' : ''}`} />}
            </button>
            <button type="button" className="flex min-w-0 flex-1 items-center gap-2 py-2 pr-2 text-left" title={item.name} aria-current={active ? 'location' : undefined} onClick={() => navigate(item.id)}>
              <Icon className="size-4 shrink-0 text-amber-600" /><span className="truncate">{item.name}</span>
            </button>
          </div>
          {children && opened && <ul className="ml-3 border-l pl-1">{branch(item.id, depth + 1,managed)}</ul>}
        </li>;
      });
  };
  const locationClass = (active: boolean) => `flex w-full items-center gap-2 rounded-md px-3 py-2 text-left ${active ? 'bg-accent text-accent-foreground' : 'hover:bg-muted'}`;
  return <nav aria-label="Árbol de ubicaciones" className="text-sm">
    <p className="px-3 pb-2 text-xs font-medium text-muted-foreground">Ubicaciones</p>
    <button className={locationClass(folder === 0)} {...dropProps(0)} aria-current={folder === 0 ? 'location' : undefined} onClick={() => navigate(0)}><HardDrive className="size-4 shrink-0 text-blue-600" />Mis archivos</button>
    <ul className="ml-2">{branch(null)}</ul>
    {folders.some(item=>item.managed)&&<><p className="px-3 pt-4 pb-2 text-xs font-medium text-muted-foreground">Documentos de ABISSOL</p><ul>{branch(null,0,true)}</ul></>}
    <div className="my-3 border-t" />
    <button className={locationClass(location === 'shared')} onClick={() => onLocation('shared')}><Share2 className="size-4 shrink-0 text-violet-600" />Compartidos conmigo</button>
    <button className={locationClass(location === 'all')} onClick={() => onLocation('all')}><FolderOpen className="size-4 shrink-0 text-amber-600" />Todos los archivos</button>
    <button className={locationClass(false)} onClick={() => onLocation('cloud')}><DriveIcon />Cuentas conectadas</button>
    <button className={locationClass(location === 'trash')} onClick={() => onLocation('trash')}><Trash2 className="size-4 shrink-0 text-muted-foreground" />Papelera</button>
  </nav>;
}
