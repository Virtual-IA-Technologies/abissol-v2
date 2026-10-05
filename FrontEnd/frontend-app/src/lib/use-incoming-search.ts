import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";

export function useIncomingSearch(enabled=true) {
  const [params] = useSearchParams();
  const incoming = enabled ? params.get("buscar") ?? "" : "";
  const [search, setSearch] = useState(incoming);
  useEffect(() => setSearch(incoming), [incoming]);
  return [search, setSearch] as const;
}
