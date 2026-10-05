import { Heart, Moon, Sparkles, Sun, SunMedium } from "lucide-react"

import { Button } from "@/components/ui/button"
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from "@/components/ui/dropdown-menu"
import { useTheme, type Theme } from "@/context/theme-context"

const themes: Array<{ value: Theme; label: string }> = [
  { value: "light", label: "Light" },
  { value: "medium", label: "Medium" },
  { value: "dark", label: "Dark" },
  { value: "virtualia", label: "Virtual IA" },
  { value: "lady", label: "Lady" },
]

export function ThemeToggle() {
  const { theme, applyTheme } = useTheme()
  const label = themes.find((option) => option.value === theme)?.label ?? "Medium"

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild className="cursor-pointer">
        <Button variant="ghost" size="icon" className="h-8 w-8 px-0" title={`Tema: ${label}`} aria-label={`Tema actual: ${label}`}>
          {theme === "light" && <Sun className="size-[1.2rem]" />}
          {theme === "medium" && <SunMedium className="size-[1.2rem]" />}
          {theme === "dark" && <Moon className="size-[1.2rem]" />}
          {theme === "virtualia" && <Sparkles className="size-[1.2rem]" />}
          {theme === "lady" && <Heart className="size-[1.2rem]" />}
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end">
        {themes.map((option) => (
          <DropdownMenuItem key={option.value} onClick={() => applyTheme(option.value)}>
            <span className="w-4" aria-hidden="true">{theme === option.value ? "✓" : ""}</span>
            {option.label}
          </DropdownMenuItem>
        ))}
      </DropdownMenuContent>
    </DropdownMenu>
  )
}
