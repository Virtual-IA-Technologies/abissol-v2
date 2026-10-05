import { useAuth } from "@/context/AuthContext";
import type { AccessLevel } from "@/features/wolverine/types";

type OptionPolicy = {
  editLevel?: AccessLevel;
  stateLevel?: AccessLevel;
  deleteLevel?: AccessLevel;
};

export function useOptionCapabilities(
  slug: string,
  policy: OptionPolicy = {},
) {
  const { can } = useAuth();
  const editLevel = policy.editLevel ?? "editor";
  const stateLevel = policy.stateLevel ?? "editor";
  const deleteLevel = policy.deleteLevel ?? "gestor";

  return {
    canRead: can(slug, "lector"),
    canEdit: can(slug, editLevel),
    canChangeState: can(slug, stateLevel),
    canDelete: can(slug, deleteLevel),
  };
}
