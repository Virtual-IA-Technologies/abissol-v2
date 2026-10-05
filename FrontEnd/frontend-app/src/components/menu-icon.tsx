import { lazy, Suspense } from "react";
import { Circle } from "lucide-react";

import {
  MENU_ICON_COMPONENTS,
  MENU_ICON_TONES,
  menuIconTone,
  normalizeMenuIconName,
} from "@/lib/menu-icons";

const AllLucideIcon = lazy(() => import("@/components/all-lucide-icon"));

export function MenuGlyph({ name, className = "size-4" }: { name: string | null; className?: string }) {
  const StaticIcon = MENU_ICON_COMPONENTS[name ?? ""];
  if (StaticIcon) return <StaticIcon className={className} />;
  const normalized = normalizeMenuIconName(name);
  if (!normalized) return <Circle className={className} />;
  return <Suspense fallback={<Circle className={className} />}><AllLucideIcon name={normalized} className={className} /></Suspense>;
}
export function MenuIcon({ name, seed, colorIndex, className = "size-4" }: { name: string | null; seed: string; colorIndex?: number; className?: string }) {
  const tone = colorIndex === undefined ? menuIconTone(seed) : MENU_ICON_TONES[colorIndex % MENU_ICON_TONES.length];
  return <span className={`inline-flex size-7 shrink-0 items-center justify-center ${tone}`}><MenuGlyph name={name} className={className} /></span>;
}
