import { useState, useRef, useEffect, type ReactNode, type MouseEvent, type DragEvent } from 'react';
import { ArrowLeft, Trash2, ClipboardPaste, FilePlus2, FolderPlus, Upload, ArrowUp, ChevronRight, FileText, Folder, Image, LayoutGrid, List, Grid2X2, TableProperties, FileSpreadsheet, Presentation } from 'lucide-react';
import { Input } from '@/components/ui/input';
import { RotateCcw, Eye, ArrowDownUp, ChevronDown, Copy, Scissors, RefreshCw, Pencil, Share2, Download, Info, PanelLeft } from 'lucide-react';
import { DropdownMenu, DropdownMenuTrigger, DropdownMenuContent, DropdownMenuRadioGroup, DropdownMenuRadioItem, DropdownMenuSeparator, DropdownMenuItem } from '@/components/ui/dropdown-menu';
import { ExplorerTree } from './explorer-tree';
import { Button } from '@/components/ui/button';
import { SearchableSelect } from '@/components/searchable-select';
import { RowActionsMenu, type RowAction } from '@/components/row-actions-menu';
import { RecordContextMenu } from '@/components/record-context-menu';
import { dateLabel, sizeLabel, type DocumentRow, type Folder as DocumentFolder } from './api';

const layouts = [
  { value: 'details', label: 'Detalles', icon: TableProperties },
  { value: 'list', label: 'Lista', icon: List },
  { value: 'medium', label: 'Iconos medianos', icon: Grid2X2 },
  { value: 'large', label: 'Iconos grandes', icon: LayoutGrid },
];

function fileIcon(row: DocumentRow) {
  if (row.file.mime.startsWith('image/')) return Image;
  if (/\.xlsx$/i.test(row.file.filename)) return FileSpreadsheet;
  if (/\.pptx$/i.test(row.file.filename)) return Presentation;
  return FileText;
}

function DocumentGlyph({row,size}:{row:DocumentRow;size:string}) {
  const Icon=fileIcon(row);
  const color=row.file.mime==='application/pdf'?'text-red-600':/\.xlsx$/i.test(row.file.filename)?'text-emerald-600':/\.pptx$/i.test(row.file.filename)?'text-orange-600':row.file.mime.startsWith('image/')?'text-violet-600':'text-blue-600';
  return <span className="relative mb-1 inline-flex shrink-0"><Icon className={`${size} ${color}`}/><span className="absolute -bottom-1 left-1/2 -translate-x-1/2 rounded border bg-background px-1 text-[9px] font-bold uppercase leading-3">{row.file.filename.split('.').pop()?.slice(0,5)}</span></span>;
}

export function Explorer({ onPurge, controls, onRefresh, onCut, search, onSearch, loading, onFiles, onRename, treeFolders, folders, folder, showFolders, query, rows, navigate, actions, open, activate, doubleClick, order, direction, sort, canEdit, canPaste, onCopy, onPaste, onMove, onCreate, onUpload, canBack, onBack, locationValue, locationOptions, onLocationChange, canManageFolders, canDeleteFolder, onDeleteFolder }: {
  controls:ReactNode; onRefresh:()=>void; onCut:(rows:DocumentRow[])=>void;
  search:string; onSearch:(value:string)=>void; loading:boolean; onFiles:(files:File[],target?:number)=>void; onRename:(row:DocumentRow)=>void;
  canBack:boolean; onBack:()=>void; locationValue:string; locationOptions:{value:string;label:string}[]; onLocationChange:(value:string)=>void; canManageFolders:boolean; canDeleteFolder:boolean; onDeleteFolder:(id:number)=>void;
  canEdit:boolean; canPaste:boolean; onCopy:(rows:DocumentRow[])=>void; onPaste:()=>void; onMove:(rows:DocumentRow[],id:number)=>void; onCreate:(kind:'file'|'folder')=>void; onUpload:()=>void;
  onPurge?:(rows:DocumentRow[])=>void; treeFolders?:DocumentFolder[]; folders: DocumentFolder[]; folder: number | undefined; showFolders: boolean; query: string; rows: DocumentRow[];
  navigate: (id: number | undefined) => void; actions: (row: DocumentRow) => RowAction[];
  open: (row: DocumentRow) => void; activate: (row: DocumentRow) => void;
  doubleClick: { value: string; choices: {value: string; label: string}[]; onChange: (value: string) => void };
  order: string; direction: string; sort: (key: string) => void;
}) {
  const [layout, setLayout] = useState(() => {
    try { const saved = localStorage.getItem('documents:layout'); return layouts.some(v => v.value === saved) ? saved! : 'medium'; }
    catch { return 'medium'; }
  });
  const [selected,setSelected]=useState<number[]>([]);
  const [selectedFolder,setSelectedFolder]=useState<number|null>(null);
  const [treeOpen,setTreeOpen]=useState(()=>{try{return localStorage.getItem('documents:tree')!=='hidden'&&window.matchMedia('(min-width: 768px)').matches;}catch{return true;}});
  const anchor=useRef<number|null>(null);
  const drag=useRef<DocumentRow[]>([]);
  const [over,setOver]=useState<number|null>(null);
  const root=useRef<HTMLDivElement>(null);
  useEffect(()=>{if(document.activeElement===document.body)root.current?.focus();},[]);
  const select=(row:DocumentRow,event?:MouseEvent)=>{setSelectedFolder(null);if(event?.shiftKey&&anchor.current!==null){const a=rows.findIndex(r=>r.id===anchor.current),b=rows.indexOf(row);setSelected(rows.slice(Math.max(0,Math.min(a,b)),Math.max(a,b)+1).map(r=>r.id));}else if(event?.ctrlKey||event?.metaKey){setSelected(old=>old.includes(row.id)?old.filter(id=>id!==row.id):[...old,row.id]);anchor.current=row.id;}else{setSelected([row.id]);anchor.current=row.id;}root.current?.focus();};
  const dropProps=(id:number)=>({
    onDragOver:(event:DragEvent)=>{if(canEdit&&(drag.current.length||event.dataTransfer.types.includes('Files'))){event.preventDefault();event.dataTransfer.dropEffect='move';setOver(id);}},
    onDragLeave:()=>setOver(null),
    onDrop:(event:DragEvent)=>{event.preventDefault();event.stopPropagation();const group=drag.current;drag.current=[];setOver(null);if(!canEdit)return;if(event.dataTransfer.files.length)onFiles(Array.from(event.dataTransfer.files),id);else if(group.length)onMove(group,id);},
    style:over===id?{outline:'2px solid var(--primary)',background:'var(--accent)'}:undefined,
  });
  const selectFolderItem=(id:number)=>{setSelected([]);setSelectedFolder(id);root.current?.focus();};
  const folderActions=(item:DocumentFolder):RowAction[]=>[
    {label:'Abrir carpeta',icon:Folder,onSelect:()=>navigate(item.id)},
    {label:item.deleted_at?'Restaurar carpeta':'Eliminar carpeta',icon:item.deleted_at?RotateCcw:Trash2,destructive:!item.deleted_at,hidden:!canManageFolders,onSelect:()=>onDeleteFolder(item.id)},
  ];
  const folderProps=(item:DocumentFolder)=>({
    ...dropProps(item.id), 'data-file':true, 'data-folder-id':item.id,
    onClick:()=>selectFolderItem(item.id),
    onContextMenu:()=>selectFolderItem(item.id),
    onDoubleClick:(event:MouseEvent)=>{if(!(event.target as HTMLElement).closest('[data-folder-actions]'))navigate(item.id);},
    style:over===item.id?dropProps(item.id).style:selectedFolder===item.id?{background:'var(--accent)',outline:'1px solid var(--primary)'}:undefined,
    title:item.name+' · Clic para seleccionar; doble clic para abrir; Suprimir para eliminar.',
  });
  const rowProps=(row:DocumentRow)=>({
    draggable:canEdit&&row.owned&&!row.deleted_at,
    'data-file':true,
    onClick:(event:MouseEvent)=>select(row,event),
    onContextMenu:()=>{if(!selected.includes(row.id))select(row);},
    onDragStart:(event:DragEvent)=>{if(!canEdit||!row.owned||row.deleted_at){event.preventDefault();return;}if(!selected.includes(row.id))select(row);drag.current=selected.includes(row.id)?rows.filter(r=>selected.includes(r.id)&&r.owned&&!r.deleted_at):[row];event.dataTransfer.effectAllowed='move';event.dataTransfer.setData('application/x-abissol-document',String(row.id));},
    onDragEnd:()=>{drag.current=[];setOver(null);},
    style:selected.includes(row.id)?{background:'var(--accent)',outline:'1px solid var(--primary)'}:undefined,
    title:row.title+' · Ctrl+clic: selección múltiple; Shift+clic: rango; F2: renombrar.',
  });
  const backgroundActions=[
    {label:'Nuevo documento',icon:FilePlus2,onSelect:()=>onCreate('file'),disabled:!canEdit},
    {label:'Nueva carpeta',icon:FolderPlus,onSelect:()=>onCreate('folder'),disabled:!canEdit},
    {label:'Subir archivo',icon:Upload,onSelect:onUpload,disabled:!canEdit},
    {label:'Pegar',icon:ClipboardPaste,onSelect:onPaste,disabled:!canEdit||!canPaste},
  ];
  const path: DocumentFolder[] = [];
  let current = folders.find(f => f.id === folder);
  const seen = new Set<number>();
  while (current && !seen.has(current.id)) {
    seen.add(current.id); path.unshift(current); current = folders.find(f => f.id === current?.parent_id);
  }
  const children = showFolders ? folders.filter(f => f.parent_id === (folder || null) && f.name.toLocaleLowerCase().includes(query.trim().toLocaleLowerCase()))
    .sort((a, b) => a.name.localeCompare(b.name, 'es', {numeric: true}) * (order === 'title' && direction === 'desc' ? -1 : 1)) : [];
  const icons = layout === 'medium' || layout === 'large';
  const iconSize = layout === 'large' ? 'size-16' : layout === 'medium' ? 'size-10' : 'size-5';
  const parent = path.at(-1)?.parent_id || 0;
  const selectedRows=rows.filter(row=>selected.includes(row.id));
  const selectedFolderRow=folders.find(item=>item.id===selectedFolder);
  const selectedActions=selectedFolderRow?folderActions(selectedFolderRow).filter(action=>!action.hidden):selectedRows.length===1?actions(selectedRows[0]).filter(action=>!action.hidden):[];
  const heading = (key: string, label: string) => <th className="px-4 py-3 text-left font-medium" aria-sort={order === key ? direction === 'asc' ? 'ascending' : 'descending' : 'none'}><button onClick={() => sort(key)}>{label} {order === key ? direction === 'asc' ? '↑' : '↓' : '↕'}</button></th>;
  return <div ref={root} tabIndex={0} aria-label="Explorador de documentos" className="outline-none" onKeyDown={event=>{
    if((event.target as HTMLElement).closest('input,textarea,[contenteditable=true],[role=combobox],[role=menu],[role=dialog]'))return;
    if(event.key==='Enter'&&event.target===root.current){if(selectedFolderRow){event.preventDefault();navigate(selectedFolderRow.id);return;}const row=rows.find(r=>selected.includes(r.id));if(row){event.preventDefault();open(row);}return;}
    if((event.ctrlKey||event.metaKey)&&event.key.toLowerCase()==='a'){event.preventDefault();setSelectedFolder(null);setSelected(rows.map(r=>r.id));return;}
    if(event.key==='Delete'&&onPurge&&selectedRows.length&&selectedRows.every(row=>row.owned&&row.deleted_at)){event.preventDefault();onPurge(selectedRows);return;}
    if(!canEdit||event.repeat)return;
    if((event.ctrlKey||event.metaKey)&&event.key.toLowerCase()==='x'&&selectedRows.length&&selectedRows.every(row=>row.owned&&!row.deleted_at)){event.preventDefault();onCut(selectedRows);return;}
    if(event.key==='Delete'){const remove=selectedActions.find(action=>action.label==='Enviar a papelera'||action.label==='Eliminar carpeta');if(remove){event.preventDefault();remove.onSelect();}return;}
    if(event.key==='F2'&&selected.length===1){const row=rows.find(r=>selected.includes(r.id));if(row?.owned&&!row.deleted_at){event.preventDefault();onRename(row);}return;}
  }} onCopy={event=>{if((event.target as HTMLElement).closest('input,textarea,[contenteditable=true],[role=dialog]')||!canEdit)return;const group=rows.filter(r=>selected.includes(r.id)&&!r.deleted_at);if(group.length){event.preventDefault();event.clipboardData.setData('text/plain','abissol-documentos');onCopy(group);}}} onPaste={event=>{if((event.target as HTMLElement).closest('input,textarea,[contenteditable=true],[role=dialog]')||!canEdit)return;const files=Array.from(event.clipboardData.files);if(files.length){event.preventDefault();onFiles(files);}else if(canPaste&&event.clipboardData.getData('text/plain')==='abissol-documentos'){event.preventDefault();onPaste();}}}>
    <div className="grid grid-cols-1 items-center gap-3 border-b bg-muted/10 p-2 md:grid-cols-2">
      <nav aria-label="Ruta de carpetas" className="flex min-w-0 items-center gap-1 text-sm">
        <Button size="icon" variant="ghost" aria-label={treeOpen?'Ocultar carpetas':'Mostrar carpetas'} aria-expanded={treeOpen} aria-controls="document-locations" onClick={()=>{setTreeOpen(!treeOpen);try{localStorage.setItem('documents:tree',treeOpen?'hidden':'visible');}catch{/* Optional preference. */}}}><PanelLeft className="size-4"/></Button>
        <Button size="icon" variant="ghost" disabled={!canBack} aria-label="Volver a la ubicación anterior" onClick={onBack}><ArrowLeft className="size-4"/></Button>
        <Button size="icon" variant="ghost" disabled={!folder} aria-label="Subir a la carpeta superior" onClick={() => navigate(parent)}><ArrowUp className="size-4"/></Button>
        <Button size="icon" variant="ghost" aria-label="Actualizar documentos" disabled={loading} onClick={onRefresh}><RefreshCw className="size-4"/></Button>
        <div className="flex min-w-0 flex-1 items-center overflow-x-auto rounded-md border bg-background">
        <div className="w-44 shrink-0" {...dropProps(0)}><SearchableSelect aria-label="Ubicación de archivos" value={locationValue} options={locationOptions} onValueChange={onLocationChange} className="h-9 min-w-0 border-transparent bg-transparent shadow-none"/></div>
        {path.map(f => <span key={f.id} className="flex shrink-0 items-center gap-1"><ChevronRight className="size-3 shrink-0"/><button className="max-w-52 truncate rounded px-2 py-1 hover:bg-muted" title={f.name} {...dropProps(f.id)} onClick={() => navigate(f.id)} aria-current={f.id === folder ? 'location' : undefined}>{f.name}</button></span>)}
        </div>
        {canDeleteFolder&&<Button className="ml-auto" size="icon" variant="ghost" aria-label="Enviar carpeta a Papelera" onClick={()=>{if(folder)onDeleteFolder(folder);}}><Trash2 className="size-4"/></Button>}
      </nav>
      <Input className="w-full min-w-0" aria-label="Buscar archivos en esta ubicación y sus subcarpetas" maxLength={100} placeholder="Buscar en esta ubicación y sus subcarpetas…" value={search} onChange={e=>onSearch(e.target.value)}/>
    </div>
    <div className="flex flex-wrap items-center gap-2 border-b p-2">
      {controls}
      {onPurge&&<Button variant="ghost" size="icon" title="Eliminar definitivamente seleccionados" aria-label="Eliminar definitivamente seleccionados" disabled={!selectedRows.length||selectedRows.some(row=>!row.owned||!row.deleted_at)} onClick={()=>onPurge(selectedRows)}><Trash2 className="size-4 text-destructive"/></Button>}
      <div className="flex items-center border-l pl-2">
        <Button size="icon" variant="ghost" title="Cortar (Ctrl+X)" aria-label="Cortar" disabled={!canEdit||!selectedRows.length||selectedRows.some(row=>!row.owned||row.deleted_at)} onClick={()=>onCut(selectedRows)}><Scissors className="size-4"/></Button>
        <Button size="icon" variant="ghost" title="Copiar (Ctrl+C)" aria-label="Copiar" disabled={!canEdit||!selectedRows.length||selectedRows.some(row=>row.deleted_at)} onClick={()=>onCopy(selectedRows)}><Copy className="size-4"/></Button>
        <Button size="icon" variant="ghost" title="Pegar (Ctrl+V)" aria-label="Pegar" disabled={!canEdit||!canPaste} onClick={onPaste}><ClipboardPaste className="size-4"/></Button>
        {([['Previsualizar',Eye],['Cambiar nombre',Pencil],['Compartir',Share2],['Descargar',Download],[selectedFolderRow?.deleted_at?'Restaurar carpeta':selectedFolderRow?'Eliminar carpeta':'Enviar a papelera',selectedFolderRow?.deleted_at?RotateCcw:Trash2],['Ver detalle e historial',Info]] as const).map(([label,Icon])=><Button key={label} size="icon" variant="ghost" aria-label={label} title={label} disabled={!selectedActions.some(action=>action.label===label)} onClick={()=>selectedActions.find(action=>action.label===label)?.onSelect()}><Icon className="size-4"/></Button>)}
      </div>

      <div className="ml-auto flex items-center gap-1">
        <DropdownMenu><DropdownMenuTrigger asChild><Button variant="ghost" aria-label="Ordenar archivos"><ArrowDownUp className="size-4"/>Ordenar<ChevronDown className="size-3"/></Button></DropdownMenuTrigger><DropdownMenuContent align="end"><DropdownMenuRadioGroup value={order} onValueChange={sort}>{[{value:'title',label:'Nombre'},{value:'size',label:'Tamaño'},{value:'updated',label:'Actualizado'}].map(item=><DropdownMenuRadioItem key={item.value} value={item.value}>{item.label}</DropdownMenuRadioItem>)}</DropdownMenuRadioGroup><DropdownMenuSeparator/><DropdownMenuItem onSelect={()=>{if(direction!=='asc')sort(order);}}>Ascendente {direction==='asc'?'✓':''}</DropdownMenuItem><DropdownMenuItem onSelect={()=>{if(direction!=='desc')sort(order);}}>Descendente {direction==='desc'?'✓':''}</DropdownMenuItem></DropdownMenuContent></DropdownMenu>
        <DropdownMenu><DropdownMenuTrigger asChild><Button variant="ghost" aria-label="Ver archivos"><LayoutGrid className="size-4"/>Ver<ChevronDown className="size-3"/></Button></DropdownMenuTrigger><DropdownMenuContent align="end"><DropdownMenuRadioGroup value={layout} onValueChange={value=>{setLayout(value);try{localStorage.setItem('documents:layout',value);}catch{/* Optional preference. */}}}>{layouts.map(item=><DropdownMenuRadioItem key={item.value} value={item.value}><item.icon className="mr-2 size-4"/>{item.label}</DropdownMenuRadioItem>)}</DropdownMenuRadioGroup></DropdownMenuContent></DropdownMenu>
      </div>
    </div>

    <div className="flex min-h-[50vh] min-w-0 flex-col md:flex-row">
      {treeOpen&&<aside id="document-locations" className="max-h-64 shrink-0 overflow-auto border-b bg-muted/10 p-2 md:max-h-[65vh] md:w-56 md:border-b-0 md:border-r"><ExplorerTree folders={treeFolders||folders} folder={locationValue==='trash'?undefined:folder} location={locationValue} navigate={id=>onLocationChange(id?'folder:'+id:'files')} onLocation={onLocationChange} dropProps={dropProps}/></aside>}
      <div className="min-w-0 flex-1">
    {loading&&<p role="status" className="px-3 py-1 text-xs text-muted-foreground">Cargando documentos…</p>}
    {selectedFolderRow&&<p className="px-3 py-1 text-xs text-muted-foreground">Carpeta seleccionada: {selectedFolderRow.name} · Doble clic o Enter para abrir</p>}
    {selected.length>0&&<p className="px-3 py-1 text-xs text-muted-foreground">{selected.length} seleccionado(s) · Ctrl+clic / Shift+clic · Ctrl+C para copiar · F2 para renombrar</p>}
    <RecordContextMenu actions={backgroundActions}><div className="min-h-80" onDragOver={event=>{if(event.dataTransfer.types.includes('Files')){event.preventDefault();event.dataTransfer.dropEffect=canEdit?'copy':'none';}}} onDrop={event=>{if(event.dataTransfer.files.length){event.preventDefault();if(canEdit)onFiles(Array.from(event.dataTransfer.files));}}} onClick={event=>{if(!(event.target as HTMLElement).closest('[data-file],button')){setSelected([]);setSelectedFolder(null);root.current?.focus();}}} onContextMenu={event=>{if(!(event.target as HTMLElement).closest('[data-file],button'))root.current?.focus();}}>
    {!children.length && !rows.length ? <div className="p-10 text-center text-sm text-muted-foreground"><Folder className="mx-auto mb-3 size-8"/>No hay elementos en esta vista.</div> : layout === 'details' ? <div className="overflow-x-auto"><table className="w-full text-sm"><thead className="border-b text-muted-foreground"><tr>{heading('title', 'Nombre')}{heading('size', 'Tamaño')}{heading('updated', 'Actualizado')}<th className="sticky right-0 bg-background px-3 text-left font-medium">Opciones</th></tr></thead><tbody>
      {children.map(f => <RecordContextMenu key={`folder-${f.id}`} actions={folderActions(f).filter(action=>!action.hidden)}><tr {...folderProps(f)} className="border-b hover:bg-muted/40"><td className="px-4 py-3"><span className="flex items-center gap-3 text-left font-medium"><Folder className="size-5 shrink-0 fill-amber-100 text-amber-600"/>{f.name}</span></td><td className="px-4 text-muted-foreground">Carpeta</td><td/><td data-folder-actions className="sticky right-0 bg-background px-3"><RowActionsMenu label={f.name} actions={folderActions(f)}/></td></tr></RecordContextMenu>)}
      {rows.map(row => { const available = actions(row).filter(a => !a.hidden); return <RecordContextMenu key={row.id} actions={available} doubleClick={doubleClick}><tr {...rowProps(row)} className="border-b hover:bg-muted/40" onDoubleClick={() => activate(row)}><td className="min-w-48 max-w-lg px-4 py-3"><div className="flex items-center gap-3"><DocumentGlyph row={row} size="size-8"/><div className="min-w-0"><button className="break-words text-left font-medium hover:underline" onClick={event => {event.stopPropagation();select(row,event);}}>{row.title}</button><p className="mt-1 truncate text-xs text-muted-foreground">v{row.current_version} · {row.owned ? 'Propio' : 'Compartido'}{row.description ? ` · ${row.description}` : ''}</p></div></div></td><td className="whitespace-nowrap px-4">{sizeLabel(row.file.size)}</td><td className="whitespace-nowrap px-4 text-xs">{dateLabel(row.updated_at)}</td><td className="sticky right-0 bg-background px-3"><RowActionsMenu label={row.title} actions={available} doubleClick={doubleClick}/></td></tr></RecordContextMenu>; })}
    </tbody></table></div> : <div className={`grid gap-2 p-3 ${layout === 'large' ? 'grid-cols-[repeat(auto-fill,minmax(160px,1fr))]' : layout === 'medium' ? 'grid-cols-[repeat(auto-fill,minmax(120px,1fr))]' : 'grid-cols-1 xl:grid-cols-2'}`}>
      {children.map(f => <RecordContextMenu key={`folder-${f.id}`} actions={folderActions(f).filter(action=>!action.hidden)}><div {...folderProps(f)} className={`relative flex min-w-0 gap-3 rounded-lg border border-transparent p-3 hover:border-border hover:bg-muted/40 ${icons ? 'flex-col items-center pt-8 text-center' : 'items-center pr-12 text-left'}`}><Folder className={`${iconSize} shrink-0 fill-amber-100 text-amber-600`}/><span title={f.name} className="w-full truncate text-sm font-medium">{f.name}</span><div data-folder-actions className="absolute right-1 top-1"><RowActionsMenu label={f.name} actions={folderActions(f)}/></div></div></RecordContextMenu>)}
      {rows.map(row => { const available = actions(row).filter(a => !a.hidden); return <RecordContextMenu key={row.id} actions={available} doubleClick={doubleClick}><div {...rowProps(row)} className={`relative flex min-w-0 gap-2 rounded-lg border border-transparent p-3 hover:border-border hover:bg-muted/40 ${icons ? 'flex-col items-center' : 'items-center'}`} onDoubleClick={() => activate(row)}><button className={`flex min-w-0 flex-1 gap-3 ${icons ? 'w-full flex-col items-center pt-5 text-center' : 'items-center text-left'}`} onClick={event => {event.stopPropagation();select(row,event);}}><DocumentGlyph row={row} size={iconSize}/><span title={row.title} className={`w-full text-sm font-medium ${icons?'line-clamp-2 h-10 break-words':'truncate'}`}>{row.title}</span></button><span className="text-xs text-muted-foreground">{sizeLabel(row.file.size)}</span><div className={icons ? 'absolute right-1 top-1' : 'shrink-0'}><RowActionsMenu label={row.title} actions={available} doubleClick={doubleClick}/></div></div></RecordContextMenu>; })}
    </div>}
    </div></RecordContextMenu>
      </div>
    </div>
  </div>;
}
