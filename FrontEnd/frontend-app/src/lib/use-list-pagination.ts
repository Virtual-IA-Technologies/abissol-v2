import { useEffect, useMemo, useState } from "react";

export type PageSize = 10 | 25 | 50 | "all";

export function useListPagination<T>(items: T[], resetKey: string) {
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState<PageSize>(10);
  const totalPages = pageSize === "all" ? 1 : Math.max(1, Math.ceil(items.length / pageSize));

  useEffect(() => { setPage(1); }, [resetKey, pageSize]);
  useEffect(() => { setPage((current) => Math.min(current, totalPages)); }, [totalPages]);

  const pageItems = useMemo(() => {
    if (pageSize === "all") return items;
    const start = (page - 1) * pageSize;
    return items.slice(start, start + pageSize);
  }, [items, page, pageSize]);

  return { pageItems, page, pageSize, totalPages, setPage, setPageSize };
}
