import { useMemo, useState } from "react";
import { Check, ChevronsUpDown } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Command, CommandEmpty, CommandGroup, CommandInput, CommandItem, CommandList } from "@/components/ui/command";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { cn } from "@/lib/utils";

export type SearchableSelectOption = {
  value: string;
  label: string;
  keywords?: string;
  disabled?: boolean;
};

type CommonProps = {
  options: SearchableSelectOption[];
  placeholder?: string;
  searchPlaceholder?: string;
  emptyMessage?: string;
  disabled?: boolean;
  className?: string;
  id?: string;
  "aria-label"?: string;
  onSearchChange?: (search: string) => void;
};

const normalize = (value: string) => value
  .normalize("NFD")
  .replace(/[\u0300-\u036f]/g, "")
  .toLocaleLowerCase("es-PE");

const commandFilter = (value: string, search: string) => normalize(value).includes(normalize(search)) ? 1 : 0;

export function SearchableSelect({
  options,
  value,
  onValueChange,
  placeholder = "Seleccionar...",
  searchPlaceholder = "Escribe para buscar...",
  emptyMessage = "No se encontraron opciones.",
  disabled,
  className,
  id,
  onSearchChange,
  "aria-label": ariaLabel,
}: CommonProps & { value: string; onValueChange: (value: string) => void }) {
  const [open, setOpen] = useState(false);
  const selected = useMemo(() => options.find((option) => option.value === value), [options, value]);

  return <Popover open={open} onOpenChange={next => { setOpen(next); if (next) onSearchChange?.(''); }}>
    <PopoverTrigger asChild>
      <Button id={id} type="button" variant="outline" role="combobox" aria-label={ariaLabel} aria-expanded={open} disabled={disabled} className={cn("h-10 w-full justify-between rounded-lg px-3 font-normal", className)}>
        <span className={cn("truncate", !selected && "text-muted-foreground")}>{selected?.label ?? placeholder}</span>
        <ChevronsUpDown className="size-4 shrink-0 opacity-50" />
      </Button>
    </PopoverTrigger>
    <PopoverContent align="start" className="w-[var(--radix-popover-trigger-width)] p-0">
      <Command filter={commandFilter} shouldFilter={!onSearchChange}>
        <CommandInput autoFocus placeholder={searchPlaceholder} onValueChange={onSearchChange} />
        <CommandList><CommandEmpty>{emptyMessage}</CommandEmpty><CommandGroup>
          {options.map((option) => <CommandItem key={option.value} value={`${option.value} ${option.label} ${option.keywords ?? ""}`} disabled={option.disabled} onSelect={() => { onValueChange(option.value); setOpen(false); }}>
            <Check className={cn("size-4", option.value === value ? "opacity-100" : "opacity-0")} />
            <span className="truncate">{option.label}</span>
          </CommandItem>)}
        </CommandGroup></CommandList>
      </Command>
    </PopoverContent>
  </Popover>;
}

export function SearchableMultiSelect({
  options,
  values,
  onValuesChange,
  placeholder = "Seleccionar...",
  searchPlaceholder = "Escribe para buscar...",
  emptyMessage = "No se encontraron opciones.",
  disabled,
  className,
  id,
  "aria-label": ariaLabel,
}: CommonProps & { values: string[]; onValuesChange: (values: string[]) => void }) {
  const [open, setOpen] = useState(false);
  const selectedLabels = useMemo(
    () => options.filter((option) => values.includes(option.value)).map((option) => option.label),
    [options, values],
  );

  return <Popover open={open} onOpenChange={setOpen}>
    <PopoverTrigger asChild>
      <Button id={id} type="button" variant="outline" role="combobox" aria-label={ariaLabel} aria-expanded={open} disabled={disabled} className={cn("h-10 w-full justify-between rounded-lg px-3 font-normal", className)}>
        <span className={cn("truncate", !selectedLabels.length && "text-muted-foreground")}>
          {selectedLabels.length ? selectedLabels.join(", ") : placeholder}
        </span>
        <span className="flex shrink-0 items-center gap-1.5">
          {values.length > 1 && <span className="rounded-full bg-muted px-1.5 py-0.5 text-[10px] font-medium">{values.length}</span>}
          <ChevronsUpDown className="size-4 opacity-50" />
        </span>
      </Button>
    </PopoverTrigger>
    <PopoverContent align="start" className="w-[var(--radix-popover-trigger-width)] p-0">
      <Command filter={commandFilter}>
        <CommandInput placeholder={searchPlaceholder} />
        <CommandList><CommandEmpty>{emptyMessage}</CommandEmpty><CommandGroup>
          {options.map((option) => {
            const selected = values.includes(option.value);
            return <CommandItem key={option.value} value={`${option.value} ${option.label} ${option.keywords ?? ""}`} disabled={option.disabled} onSelect={() => onValuesChange(selected ? values.filter((item) => item !== option.value) : [...values, option.value])}>
              <Check className={cn("size-4", selected ? "opacity-100" : "opacity-0")} />
              <span className="truncate">{option.label}</span>
            </CommandItem>;
          })}
        </CommandGroup></CommandList>
      </Command>
    </PopoverContent>
  </Popover>;
}
