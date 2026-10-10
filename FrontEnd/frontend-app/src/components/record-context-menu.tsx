import { ChevronRight, Circle, MousePointer2, type LucideIcon } from "lucide-react";
import { useRef, useState, type ReactNode } from "react";
import { Dialog,DialogContent,DialogHeader,DialogTitle,DialogDescription } from "@/components/side-dialog";
import { ContextMenu } from "radix-ui";

import type { DoubleClickChoice } from "@/components/row-actions-menu";

export interface RecordContextAction {
  label: string;
  icon?: LucideIcon;
  onSelect: () => void;
  disabled?: boolean;
  destructive?: boolean;
}

export function RecordContextMenu<T extends string>({ children, actions, doubleClick, dynamic = false }: {
  children: ReactNode;
  actions: RecordContextAction[];
  dynamic?: boolean;
  doubleClick?: {
    value: T;
    choices: DoubleClickChoice<T>[];
    onChange: (value: T) => void;
  };
}) {
  const [preview,setPreview]=useState<string|null>(null);
  const trigger=useRef<HTMLElement|null>(null);
  const permitted=actions.filter(action=>!action.disabled);
  const fallback=!dynamic&&!permitted.some(action=>!action.destructive);
  const showPreview=()=>setPreview(trigger.current?.innerText||"Sin datos adicionales.");
  const visible:RecordContextAction[]=fallback?[{label:"Ver detalle",onSelect:showPreview},...permitted]:permitted;
  return <><ContextMenu.Root><ContextMenu.Trigger asChild ref={node=>{trigger.current=node;}} tabIndex={fallback?0:undefined} onDoubleClickCapture={event=>{if(fallback&&!(event.target as Element).closest('button,a,input,textarea')){event.stopPropagation();showPreview();}}} onKeyDown={event=>{if(fallback&&event.key==="Enter"&&event.target===event.currentTarget){event.preventDefault();showPreview();}}}>{children}</ContextMenu.Trigger><ContextMenu.Portal><ContextMenu.Content className="bg-popover text-popover-foreground z-50 min-w-44 rounded-lg border p-1 shadow-lg">
    {visible.map((action) => { const Icon = action.icon; return <ContextMenu.Item key={action.label} className={`flex cursor-default select-none items-center gap-2 rounded-md px-2.5 py-2 text-sm outline-none focus:bg-accent ${action.destructive ? "text-destructive" : ""}`} onSelect={action.onSelect}>{Icon && <Icon className="size-4" />}{action.label}</ContextMenu.Item>; })}
    {doubleClick && <>
      {visible.length > 0 && <ContextMenu.Separator className="bg-border -mx-1 my-1 h-px" />}
      <ContextMenu.Sub>
        <ContextMenu.SubTrigger className="flex cursor-default select-none items-center gap-2 rounded-md px-2.5 py-2 text-sm outline-none focus:bg-accent data-[state=open]:bg-accent"><MousePointer2 className="size-4 text-muted-foreground" />Acción del doble clic<ChevronRight className="ml-auto size-4" /></ContextMenu.SubTrigger>
        <ContextMenu.Portal><ContextMenu.SubContent className="bg-popover text-popover-foreground z-50 min-w-48 rounded-lg border p-1 shadow-lg">
          <ContextMenu.RadioGroup value={doubleClick.value} onValueChange={(value) => doubleClick.onChange(value as T)}>
            {doubleClick.choices.filter(choice=>choice.value!=='none').map((choice) => <ContextMenu.RadioItem key={choice.value} value={choice.value} className="relative flex cursor-default select-none items-center rounded-md py-2 pl-8 pr-2.5 text-sm outline-none focus:bg-accent"><span className="absolute left-2.5 flex size-3.5 items-center justify-center"><ContextMenu.ItemIndicator><Circle className="size-2 fill-current" /></ContextMenu.ItemIndicator></span>{choice.label}</ContextMenu.RadioItem>)}
          </ContextMenu.RadioGroup>
        </ContextMenu.SubContent></ContextMenu.Portal>
      </ContextMenu.Sub>
    </>}
  </ContextMenu.Content></ContextMenu.Portal></ContextMenu.Root><Dialog open={preview!==null} onOpenChange={open=>{if(!open)setPreview(null);}}><DialogContent><DialogHeader><DialogTitle>Detalle del registro</DialogTitle><DialogDescription>Consulta de la información visible; sin modificar el registro.</DialogDescription></DialogHeader><p className="max-h-96 overflow-auto whitespace-pre-wrap text-sm">{preview}</p></DialogContent></Dialog></>;
}
