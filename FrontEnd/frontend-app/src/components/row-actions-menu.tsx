import { MousePointer2, MoreVertical, type LucideIcon } from "lucide-react";

import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuRadioGroup,
  DropdownMenuRadioItem,
  DropdownMenuSeparator,
  DropdownMenuSub,
  DropdownMenuSubContent,
  DropdownMenuSubTrigger,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";

export interface RowAction {
  label: string;
  icon?: LucideIcon;
  onSelect: () => void;
  destructive?: boolean;
  hidden?: boolean;
}

export interface DoubleClickChoice<T extends string> {
  value: T;
  label: string;
}

export function RowActionsMenu<T extends string>({
  label,
  actions,
  doubleClick,
}: {
  label: string;
  actions: RowAction[];
  doubleClick?: {
    value: T;
    choices: DoubleClickChoice<T>[];
    onChange: (value: T) => void;
  };
}) {
  const visibleActions = actions.filter((action) => !action.hidden);

  return <DropdownMenu>
    <DropdownMenuTrigger asChild>
      <Button
        type="button"
        variant="outline"
        size="icon"
        className="size-8"
        aria-label={`Opciones de ${label}`}
        title="Más opciones"
        onClick={(event) => event.stopPropagation()}
        onDoubleClick={(event) => event.stopPropagation()}
      >
        <MoreVertical className="size-4" />
      </Button>
    </DropdownMenuTrigger>
    <DropdownMenuContent align="end" className="min-w-52">
      {visibleActions.map((action) => {
        const Icon = action.icon;
        return <DropdownMenuItem key={action.label} variant={action.destructive ? "destructive" : "default"} onSelect={action.onSelect}>
          {Icon && <Icon />}{action.label}
        </DropdownMenuItem>;
      })}
      {doubleClick && <>
        {visibleActions.length > 0 && <DropdownMenuSeparator />}
        <DropdownMenuSub>
          <DropdownMenuSubTrigger><MousePointer2 className="mr-2 size-4 text-muted-foreground" />Acción del doble clic</DropdownMenuSubTrigger>
          <DropdownMenuSubContent className="min-w-48">
            <DropdownMenuRadioGroup value={doubleClick.value} onValueChange={(value) => doubleClick.onChange(value as T)}>
              {doubleClick.choices.filter(choice=>choice.value!=='none').map((choice) => <DropdownMenuRadioItem key={choice.value} value={choice.value}>{choice.label}</DropdownMenuRadioItem>)}
            </DropdownMenuRadioGroup>
          </DropdownMenuSubContent>
        </DropdownMenuSub>
      </>}
    </DropdownMenuContent>
  </DropdownMenu>;
}
