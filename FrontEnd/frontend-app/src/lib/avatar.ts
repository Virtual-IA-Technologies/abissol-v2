import { API_ROOT } from "@/lib/api";

export function avatarUrl(filename: string | null | undefined) {
  return filename ? `${API_ROOT}/avatars/${encodeURIComponent(filename)}` : "";
}
