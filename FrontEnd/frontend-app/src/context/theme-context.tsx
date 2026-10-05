import type React from "react"
import { createContext, useContext, useLayoutEffect, useRef, useState } from "react"
import { toast } from "sonner"

import { useAuth } from "@/context/AuthContext"
import { wolverineAPI } from "@/features/wolverine/api"
import type { NavigationLayout } from "@/features/wolverine/types"

export type Theme = "light" | "medium" | "dark" | "virtualia" | "lady"
export type MenuPalette = "theme" | "custom"
export type BackgroundPalette = "theme" | "custom"
export type ThemeAppearance = {
  menu_palette: MenuPalette
  background_palette: BackgroundPalette
  menu_color: string
  menu_tone: number
  background_color: string
  background_tone: number
}
type AppearanceOverrides = Partial<Record<Theme, ThemeAppearance>>

type ThemeProviderContextType = {
  theme: Theme
  applyTheme: (theme: Theme) => void
  menuPalette: MenuPalette
  applyMenuPalette: (palette: MenuPalette) => void
  backgroundPalette: BackgroundPalette
  applyBackgroundPalette: (palette: BackgroundPalette) => void
  menuColor: string
  applyMenuColor: (color: string) => void
  menuTone: number
  applyMenuTone: (tone: number) => void
  backgroundColor: string
  applyBackgroundColor: (color: string) => void
  backgroundTone: number
  applyBackgroundTone: (tone: number) => void
  scale: number
  applyScale: (scale: number) => void
  navigationLayout: NavigationLayout
  applyNavigationLayout: (layout: NavigationLayout) => void
  savePreferences: () => Promise<void>
}

const ThemeProviderContext = createContext<ThemeProviderContextType | undefined>(undefined)
const themes: Theme[] = ["light", "medium", "dark", "virtualia", "lady"]
const menuPalettes: MenuPalette[] = ["theme", "custom"]
const backgroundPalettes: BackgroundPalette[] = ["theme", "custom"]
const navigationLayouts: NavigationLayout[] = ["sidebar", "icons", "top"]

const themeDefaults: Record<Theme, ThemeAppearance> = {
  light: { menu_palette: "theme", background_palette: "theme", menu_color: "#fafafa", menu_tone: 50, background_color: "#ffffff", background_tone: 50 },
  medium: { menu_palette: "theme", background_palette: "theme", menu_color: "#272727", menu_tone: 50, background_color: "#ffffff", background_tone: 50 },
  dark: { menu_palette: "theme", background_palette: "theme", menu_color: "#2b2b2b", menu_tone: 50, background_color: "#181818", background_tone: 50 },
  virtualia: { menu_palette: "theme", background_palette: "theme", menu_color: "#071827", menu_tone: 50, background_color: "#081a2a", background_tone: 50 },
  lady: { menu_palette: "theme", background_palette: "theme", menu_color: "#ecdeef", menu_tone: 50, background_color: "#fff9fc", background_tone: 50 },
}

function normalizeTheme(value: string | null, fallback: Theme): Theme {
  if (themes.includes(value as Theme)) return value as Theme
  if (value === "system") return "medium"
  return fallback
}

function normalizeMenuPalette(value: unknown): MenuPalette {
  return menuPalettes.includes(value as MenuPalette) ? value as MenuPalette : "theme"
}

function normalizeBackgroundPalette(value: unknown): BackgroundPalette {
  return backgroundPalettes.includes(value as BackgroundPalette) ? value as BackgroundPalette : "theme"
}

function normalizedColor(value: unknown, fallback: string) {
  return typeof value === "string" && /^#[0-9a-f]{6}$/i.test(value) ? value.toLowerCase() : fallback
}

function normalizedTone(value: unknown, fallback = 50) {
  const number = Number(value)
  return Number.isFinite(number) ? Math.max(0, Math.min(100, Math.round(number))) : fallback
}

function normalizeNavigationLayout(value: unknown): NavigationLayout {
  return navigationLayouts.includes(value as NavigationLayout) ? value as NavigationLayout : "sidebar"
}

function normalizeAppearance(theme: Theme, value?: Partial<ThemeAppearance> | null): ThemeAppearance {
  const fallback = themeDefaults[theme]
  const menuPalette = normalizeMenuPalette(value?.menu_palette)
  const backgroundPalette = normalizeBackgroundPalette(value?.background_palette)
  return {
    menu_palette: menuPalette,
    background_palette: backgroundPalette,
    menu_color: menuPalette === "theme" ? fallback.menu_color : normalizedColor(value?.menu_color, fallback.menu_color),
    menu_tone: menuPalette === "theme" ? fallback.menu_tone : normalizedTone(value?.menu_tone, fallback.menu_tone),
    background_color: backgroundPalette === "theme" ? fallback.background_color : normalizedColor(value?.background_color, fallback.background_color),
    background_tone: backgroundPalette === "theme" ? fallback.background_tone : normalizedTone(value?.background_tone, fallback.background_tone),
  }
}

function normalizeOverrides(value: unknown): AppearanceOverrides {
  if (!value || typeof value !== "object" || Array.isArray(value)) return {}
  const source = value as Record<string, Partial<ThemeAppearance>>
  return Object.fromEntries(themes.filter((theme) => source[theme]).map((theme) => [theme, normalizeAppearance(theme, source[theme])])) as AppearanceOverrides
}

function storedOverrides(): AppearanceOverrides {
  try { return normalizeOverrides(JSON.parse(localStorage.getItem("appearance-overrides") || "{}")) } catch { return {} }
}

function setDocumentTheme(theme: Theme) {
  const root = document.documentElement
  root.classList.remove(...themes)
  root.classList.add(theme)
  root.style.colorScheme = theme === "dark" || theme === "virtualia" ? "dark" : "light"
}

function mixHex(color: string, target: "#000000" | "#ffffff", amount: number) {
  const source = color.slice(1).match(/.{2}/g)!.map((part) => Number.parseInt(part, 16))
  const destination = target === "#ffffff" ? [255, 255, 255] : [0, 0, 0]
  return `#${source.map((channel, index) => Math.round(channel + (destination[index] - channel) * amount).toString(16).padStart(2, "0")).join("")}`
}

function tonedColor(color: string, tone: number) {
  const distance = Math.abs(tone - 50) / 50
  return mixHex(color, tone >= 50 ? "#ffffff" : "#000000", distance * 0.72)
}

function readableText(color: string) {
  const [red, green, blue] = color.slice(1).match(/.{2}/g)!.map((part) => Number.parseInt(part, 16) / 255)
  return 0.2126 * red + 0.7152 * green + 0.0722 * blue > 0.56 ? "#302633" : "#f5fbff"
}

function setDocumentAppearance(appearance: ThemeAppearance) {
  const root = document.documentElement
  root.classList.remove(...menuPalettes.map((value) => `menu-${value}`), ...backgroundPalettes.map((value) => `background-${value}`))
  root.classList.add(`menu-${appearance.menu_palette}`, `background-${appearance.background_palette}`)
  const menuSurface = tonedColor(appearance.menu_color, appearance.menu_tone)
  const menuForeground = readableText(menuSurface)
  const backgroundSurface = tonedColor(appearance.background_color, appearance.background_tone)
  const backgroundForeground = readableText(backgroundSurface)
  root.style.setProperty("--custom-menu-surface", menuSurface)
  root.style.setProperty("--custom-menu-accent", mixHex(menuSurface, menuForeground === "#f5fbff" ? "#ffffff" : "#000000", 0.14))
  root.style.setProperty("--custom-menu-foreground", menuForeground)
  root.style.setProperty("--custom-menu-color", appearance.menu_color)
  root.style.setProperty("--custom-menu-primary-foreground", readableText(appearance.menu_color))
  root.style.setProperty("--custom-background-surface", `radial-gradient(circle at 80% 8%, ${mixHex(appearance.background_color, "#ffffff", 0.35)} 0, transparent 32rem), linear-gradient(145deg, ${mixHex(backgroundSurface, "#ffffff", 0.12)}, ${mixHex(backgroundSurface, "#000000", 0.08)})`)
  root.style.setProperty("--custom-background-foreground", backgroundForeground)
}

export function ThemeProvider({
  children,
  defaultTheme = "medium",
  ...props
}: {
  children: React.ReactNode
  defaultTheme?: Theme
}) {
  const { user, refreshSession } = useAuth()
  const initialTheme = normalizeTheme(localStorage.getItem("theme"), defaultTheme)
  const initialOverrides = storedOverrides()
  const [theme, setTheme] = useState<Theme>(initialTheme)
  const [appearanceOverrides, setAppearanceOverrides] = useState<AppearanceOverrides>(initialOverrides)
  const [appearance, setAppearance] = useState<ThemeAppearance>(() => normalizeAppearance(initialTheme, initialOverrides[initialTheme]))
  const [scale, setScale] = useState(100)
  const [navigationLayout, setNavigationLayout] = useState<NavigationLayout>(() => normalizeNavigationLayout(localStorage.getItem("navigation-layout")))
  const overridesRef = useRef(appearanceOverrides)
  const saveSequence = useRef(0)
  const profile = user
  const profileTheme = profile?.tema
  const ownerId = profile?.id
  const owner = useRef(ownerId)
  owner.current = ownerId
  const themeQueue = useRef<Promise<unknown>>(Promise.resolve())

  const replaceOverrides = (next: AppearanceOverrides) => {
    overridesRef.current = next
    setAppearanceOverrides(next)
    localStorage.setItem("appearance-overrides", JSON.stringify(next))
  }

  const updateCurrentAppearance = (patch: Partial<ThemeAppearance>) => {
    const nextAppearance = normalizeAppearance(theme, { ...appearance, ...patch })
    replaceOverrides({ ...overridesRef.current, [theme]: nextAppearance })
    setAppearance(nextAppearance)
    setDocumentAppearance(nextAppearance)
  }

  const applyScale = (value: number) => {
    const next = Number.isFinite(value) ? Math.max(80, Math.min(120, Math.round(value / 5) * 5)) : 100
    setScale(next)
    document.documentElement.style.fontSize = `${next}%`

  }

  const applyTheme = (newTheme: Theme) => {
    if (newTheme === theme) return
    const previousTheme = theme
    const sequence = ++saveSequence.current
    const nextAppearance = normalizeAppearance(newTheme, overridesRef.current[newTheme])
    setDocumentTheme(newTheme)
    setDocumentAppearance(nextAppearance)
    localStorage.setItem("theme", newTheme)
    setTheme(newTheme)
    setAppearance(nextAppearance)
    if (!user) return
    themeQueue.current = themeQueue.current.catch(() => undefined).then(() => {
      if (owner.current !== ownerId) return
      return wolverineAPI.updateMyTheme(newTheme)
    }).catch(() => {
      if (saveSequence.current !== sequence || owner.current !== ownerId) return
      const previousAppearance = normalizeAppearance(previousTheme, overridesRef.current[previousTheme])
      setDocumentTheme(previousTheme)
      setDocumentAppearance(previousAppearance)
      localStorage.setItem("theme", previousTheme)
      setTheme(previousTheme)
      setAppearance(previousAppearance)
      toast.error("No se pudo guardar el tema en tu perfil")
    })
  }

  const applyNavigationLayout = (value: NavigationLayout) => {
    const next = normalizeNavigationLayout(value)
    setNavigationLayout(next)
    localStorage.setItem("navigation-layout", next)
  }

  const savePreferences = async () => {
    if (!ownerId) throw Error('Inicia sesión para guardar tus preferencias')
    await themeQueue.current
    if (owner.current !== ownerId) throw Error('La sesión cambió; vuelve a guardar desde tu cuenta')
    const current = normalizeAppearance(theme, overridesRef.current[theme])
    await wolverineAPI.updateMyPreferences({
      tema: theme, escala: scale, navigation_layout: navigationLayout,
      menu_palette: current.menu_palette, background_palette: current.background_palette,
      menu_color: current.menu_color, menu_tone: current.menu_tone,
      background_color: current.background_color, background_tone: current.background_tone,
      appearance_overrides: overridesRef.current,
    })
    await refreshSession()
  }

  useLayoutEffect(() => {
    setDocumentTheme(initialTheme)
    setDocumentAppearance(normalizeAppearance(initialTheme, initialOverrides[initialTheme]))
    localStorage.setItem("theme", initialTheme)
  // La carga inicial solo debe ejecutarse al montar el proveedor.
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [defaultTheme])

  useLayoutEffect(() => {
    const next = ownerId ? Number(profile?.escala ?? 100) : 100
    applyScale(Number.isFinite(next) && next >= 80 && next <= 120 ? next : 100)
    if (!ownerId) return
    const nextLayout = normalizeNavigationLayout(profile?.navigation_layout)
    setNavigationLayout(nextLayout)
    localStorage.setItem("navigation-layout", nextLayout)
  }, [ownerId, profile?.escala, profile?.navigation_layout])

  useLayoutEffect(() => {
    if (!ownerId || !profileTheme) return
    const savedTheme = normalizeTheme(profileTheme, "medium")
    let savedOverrides = normalizeOverrides(profile?.appearance_overrides)
    if (!savedOverrides[savedTheme]) {
      savedOverrides = { ...savedOverrides, [savedTheme]: normalizeAppearance(savedTheme, {
        menu_palette: profile?.menu_palette, background_palette: profile?.background_palette,
        menu_color: profile?.menu_color, menu_tone: profile?.menu_tone,
        background_color: profile?.background_color, background_tone: profile?.background_tone,
      }) }
    }
    const savedAppearance = normalizeAppearance(savedTheme, savedOverrides[savedTheme])
    replaceOverrides(savedOverrides)
    setTheme(savedTheme)
    setAppearance(savedAppearance)
    setDocumentTheme(savedTheme)
    setDocumentAppearance(savedAppearance)
    localStorage.setItem("theme", savedTheme)
  }, [ownerId, profileTheme, profile?.appearance_overrides, profile?.menu_palette, profile?.background_palette, profile?.menu_color, profile?.menu_tone, profile?.background_color, profile?.background_tone])

  return (
    <ThemeProviderContext.Provider value={{
      theme, applyTheme,
      menuPalette: appearance.menu_palette, applyMenuPalette: (value) => updateCurrentAppearance({ menu_palette: normalizeMenuPalette(value) }),
      backgroundPalette: appearance.background_palette, applyBackgroundPalette: (value) => updateCurrentAppearance({ background_palette: normalizeBackgroundPalette(value) }),
      menuColor: appearance.menu_color, applyMenuColor: (value) => updateCurrentAppearance({ menu_color: normalizedColor(value, appearance.menu_color) }),
      menuTone: appearance.menu_tone, applyMenuTone: (value) => updateCurrentAppearance({ menu_tone: normalizedTone(value, appearance.menu_tone) }),
      backgroundColor: appearance.background_color, applyBackgroundColor: (value) => updateCurrentAppearance({ background_color: normalizedColor(value, appearance.background_color) }),
      backgroundTone: appearance.background_tone, applyBackgroundTone: (value) => updateCurrentAppearance({ background_tone: normalizedTone(value, appearance.background_tone) }),
      scale, applyScale, navigationLayout, applyNavigationLayout, savePreferences,
    }} {...props}>
      {children}
    </ThemeProviderContext.Provider>
  )
}

export const useTheme = () => {
  const context = useContext(ThemeProviderContext)
  if (context === undefined) throw new Error("useTheme must be used within a ThemeProvider")
  return context
}
