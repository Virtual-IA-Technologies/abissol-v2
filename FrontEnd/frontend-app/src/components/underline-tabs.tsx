import { useId, type ReactNode } from "react";

type Tab = { value: string; label: string; icon?: ReactNode };

export function UnderlineTabs({ label, value, onChange, tabs, children }: {
  label: string; value: string; onChange: (value: string) => void; tabs: Tab[]; children: ReactNode;
}) {
  const id = useId();
  if (!tabs.length) return children;
  return <>
    <div role="tablist" aria-label={label} className="flex overflow-x-auto border-b">
      {tabs.map((tab, index) => <button key={tab.value} type="button" role="tab"
        id={`${id}-${tab.value}`} aria-controls={`${id}-panel`} aria-selected={value === tab.value}
        tabIndex={value === tab.value ? 0 : -1}
        className={`flex shrink-0 items-center gap-2 border-b-2 px-4 py-3 text-sm transition-colors focus-visible:outline-2 focus-visible:outline-offset-[-3px] focus-visible:outline-emerald-600 ${value === tab.value ? "border-emerald-600 font-medium text-emerald-700 dark:text-emerald-400" : "border-transparent text-muted-foreground hover:border-muted-foreground/30 hover:text-foreground"}`}
        onClick={() => onChange(tab.value)} onKeyDown={event => {
          const next = event.key === "ArrowRight" ? (index + 1) % tabs.length : event.key === "ArrowLeft" ? (index - 1 + tabs.length) % tabs.length : event.key === "Home" ? 0 : event.key === "End" ? tabs.length - 1 : -1;
          if (next < 0) return;
          event.preventDefault();
          onChange(tabs[next].value);
          document.getElementById(`${id}-${tabs[next].value}`)?.focus();
        }}>{tab.icon}{tab.label}</button>)}
    </div>
    <div role="tabpanel" id={`${id}-panel`} aria-labelledby={`${id}-${value}`} tabIndex={0} className="space-y-6">{children}</div>
  </>;
}
