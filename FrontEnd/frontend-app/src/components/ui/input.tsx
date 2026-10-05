import * as React from "react"
import { X } from "lucide-react"
import { clearTextInput, useClearTextInput } from "@/lib/clear-text-input"

import { cn } from "@/lib/utils"

function Input({ className, type, ref, onChange, clearButtonClassName, ...props }: React.ComponentProps<"input"> & {clearButtonClassName?: string}) {
  const local = React.useRef<HTMLInputElement>(null)
  const [uncontrolled, setUncontrolled] = React.useState(String(props.defaultValue ?? ""))
  const clearable = ["text", "search", "email", "tel", "url"].includes(type ?? "text") && !props.disabled && !props.readOnly
  const filled = String(props.value ?? uncontrolled).length > 0
  useClearTextInput(local, clearable)
  const input = (
    <input
      ref={node => {local.current = node; if (typeof ref === "function") return ref(node); else if (ref) ref.current = node}}
      type={type}
      data-slot="input"
      className={cn(
        "file:text-foreground placeholder:text-muted-foreground/75 selection:bg-primary selection:text-primary-foreground dark:bg-input/30 border-input h-10 w-full min-w-0 rounded-lg border bg-background px-3.5 py-2 text-base shadow-xs transition-[color,box-shadow] outline-none file:inline-flex file:h-7 file:border-0 file:bg-transparent file:text-sm file:font-medium disabled:pointer-events-none disabled:cursor-not-allowed disabled:opacity-50 md:text-sm",
        "focus-visible:border-ring focus-visible:ring-ring/50 focus-visible:ring-[3px]",
        "aria-invalid:ring-destructive/20 dark:aria-invalid:ring-destructive/40 aria-invalid:border-destructive",
        clearable && "col-start-1 row-start-1 pr-10",
        className
      )}
      {...props}
      onChange={event => {setUncontrolled(event.target.value); onChange?.(event)}}
    />
  )
  if (!clearable) return input
  return <span className="grid w-full min-w-0 items-center">
    {input}
    {filled && <button type="button" tabIndex={0} aria-label={`Limpiar ${props["aria-label"] ?? props.placeholder ?? "texto"}`} title="Limpiar texto (Esc)" className={cn("z-10 col-start-1 row-start-1 mr-2 flex size-6 items-center justify-center justify-self-end rounded text-muted-foreground hover:bg-muted focus-visible:outline-2", clearButtonClassName)} onPointerDown={event => event.preventDefault()} onClick={() => {if (local.current) clearTextInput(local.current)}}><X className="size-3.5"/></button>}
  </span>
}

export { Input }
