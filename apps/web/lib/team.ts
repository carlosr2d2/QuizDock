import type { MembershipRole } from "@/types/api";

export const roleLabel: Record<MembershipRole, string> = {
  owner: "propietario",
  admin: "admin",
  member: "miembro",
  auditor: "auditor",
};

export const inviteRoles: MembershipRole[] = ["member", "admin", "auditor"];
