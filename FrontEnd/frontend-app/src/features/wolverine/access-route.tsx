import type { ReactNode } from "react";
import { Navigate } from "react-router-dom";

import { useAuth } from "@/context/AuthContext";
import type { AccessLevel } from "./types";

export function AccessRoute({ menu, minimum = "lector", children }: { menu: string | string[]; minimum?: AccessLevel; children: ReactNode }) {
  const { can, loading } = useAuth();
  if (loading) return null;
  return (Array.isArray(menu) ? menu : [menu]).some(slug => can(slug, minimum)) ? children : <Navigate to="/inicio" replace />;
}
