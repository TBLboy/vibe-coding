import { validateSyncPath } from "../../shared/team-contracts/layout.ts";
export const validateWorkspacePath = validateSyncPath;
export type WorkspacePathCheck = ReturnType<typeof validateSyncPath>;
