import { useMemo, useState } from "react";

import type { DoubleClickChoice } from "@/components/row-actions-menu";
import type { AccessLevel } from "@/features/wolverine/types";
import { useDoubleClickPreference } from "@/lib/use-double-click-preference";
import { useIncomingSearch } from "@/lib/use-incoming-search";
import { useListPagination } from "@/lib/use-list-pagination";
import { useOptionCapabilities } from "@/lib/use-option-capabilities";

export type StandardPanelMode = "create" | "view" | "edit";

type StandardOptionPolicy = {
  editLevel?: AccessLevel;
  stateLevel?: AccessLevel;
  deleteLevel?: AccessLevel;
};

export function useStandardOptionWorkspace<T, A extends string>({
  slug,
  items,
  doubleClickChoices,
  defaultDoubleClick,
  policy,
  incomingSearch=true,
}: {
  slug: string;
  items: T[];
  doubleClickChoices: readonly DoubleClickChoice<A>[];
  defaultDoubleClick: A;
  policy?: StandardOptionPolicy;
  incomingSearch?: boolean;
}) {
  const capabilities = useOptionCapabilities(slug, policy);
  const [search, setSearch] = useIncomingSearch(incomingSearch);
  const [quickFilter, setQuickFilter] = useState("all");
  const [sortKey, setSortKey] = useState("");
  const [sortDirection, setSortDirection] = useState<"asc" | "desc">("asc");
  const [panel, setPanel] = useState<{ mode: StandardPanelMode; record: T | null } | null>(null);
  const [doubleClickAction, setDoubleClickAction] = useDoubleClickPreference<A>(
    slug,
    doubleClickChoices.map((choice) => choice.value),
    defaultDoubleClick,
  );
  const resetKey = `${search}\u0000${quickFilter}\u0000${sortKey}\u0000${sortDirection}`;
  const pagination = useListPagination(items, resetKey);
  const doubleClick = useMemo(() => ({
    value: doubleClickAction,
    choices: [...doubleClickChoices],
    onChange: setDoubleClickAction,
  }), [doubleClickAction, doubleClickChoices, setDoubleClickAction]);

  function toggleSort(nextKey: string) {
    if (sortKey === nextKey) setSortDirection((current) => current === "asc" ? "desc" : "asc");
    else {
      setSortKey(nextKey);
      setSortDirection("asc");
    }
  }

  return {
    ...capabilities,
    search,
    setSearch,
    quickFilter,
    setQuickFilter,
    sortKey,
    sortDirection,
    toggleSort,
    panel,
    openCreate: () => setPanel({ mode: "create", record: null }),
    openView: (record: T) => setPanel({ mode: "view", record }),
    openEdit: (record: T) => setPanel({ mode: "edit", record }),
    closePanel: () => setPanel(null),
    doubleClick,
    ...pagination,
  };
}
