import type * as React from "react";

import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

export type ActionTone = "info" | "new" | "edit" | "delete" | "excel";

const toneClasses: Record<ActionTone, string> = {
  info: "border-sky-200 bg-sky-50/70 text-sky-700 hover:border-sky-300 hover:bg-sky-100 hover:text-sky-800 dark:border-sky-900 dark:bg-sky-950/40 dark:text-sky-300",
  new: "border-sky-200 bg-sky-50/70 text-sky-700 hover:border-sky-300 hover:bg-sky-100 hover:text-sky-800 dark:border-sky-900 dark:bg-sky-950/40 dark:text-sky-300",
  edit: "border-amber-200 bg-amber-50/70 text-amber-700 hover:border-amber-300 hover:bg-amber-100 hover:text-amber-800 dark:border-amber-900 dark:bg-amber-950/40 dark:text-amber-300",
  delete: "border-red-200 bg-red-50/70 text-red-700 hover:border-red-300 hover:bg-red-100 hover:text-red-800 dark:border-red-900 dark:bg-red-950/40 dark:text-red-300",
  excel: "border-green-200 bg-green-50/70 text-green-700 hover:border-green-300 hover:bg-green-100 hover:text-green-800 dark:border-green-900 dark:bg-green-950/40 dark:text-green-300",
};

export function ActionButton({ tone = "info", className, ...props }: React.ComponentProps<typeof Button> & { tone?: ActionTone }) {
  return <Button variant="outline" className={cn(toneClasses[tone], className)} {...props} />;
}
