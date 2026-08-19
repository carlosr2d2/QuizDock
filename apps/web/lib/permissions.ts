import { getOrgId } from "@/lib/session";
import type { User } from "@/types/api";

export function currentRole(user?: User | null): User["memberships"][number]["role"] | null {
  if (!user) return null;
  const orgId = getOrgId();
  return user.memberships.find((item) => item.organization_id === orgId)?.role ?? null;
}

export function canCreateContent(user?: User | null): boolean {
  const role = currentRole(user);
  return role === "owner" || role === "admin";
}
