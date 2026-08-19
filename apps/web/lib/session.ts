const TOKEN_KEY = "qd_token";
const ORG_KEY = "qd_org";
const USER_KEY = "qd_user";

export function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(TOKEN_KEY);
}

export function getOrgId(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(ORG_KEY);
}

async function syncSessionCookie(method: "POST" | "DELETE") {
  const response = await fetch("/api/session", { method, credentials: "same-origin" });
  if (!response.ok) {
    throw new Error("No se pudo guardar la sesión");
  }
}

export async function setSession(token: string, orgId: string, userJson: string) {
  localStorage.setItem(TOKEN_KEY, token);
  localStorage.setItem(ORG_KEY, orgId);
  localStorage.setItem(USER_KEY, userJson);
  await syncSessionCookie("POST");
}

export function switchOrganization(orgId: string) {
  if (typeof window === "undefined") return;
  localStorage.setItem(ORG_KEY, orgId);
  window.location.reload();
}

export function inviteTokenFromNext(next: string | null): string | null {
  if (!next) return null;
  const match = next.match(/^\/invite\/([^/?#]+)/);
  return match?.[1] ?? null;
}

export function authWorkspaceId(user: { personal_organization_id: string | null; memberships: { organization_id: string }[] }, preferred?: string | null): string {
  if (preferred && user.memberships.some((item) => item.organization_id === preferred)) {
    return preferred;
  }
  return user.personal_organization_id ?? user.memberships[0]?.organization_id ?? "";
}

export async function clearSession() {
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(ORG_KEY);
  localStorage.removeItem(USER_KEY);
  document.cookie = `${TOKEN_KEY}=; Path=/; Max-Age=0; SameSite=Lax`;
  await fetch("/api/session", { method: "DELETE", credentials: "same-origin" }).catch(() => undefined);
}

let redirectingToLogin = false;

export async function redirectToLogin(nextPath?: string) {
  if (typeof window === "undefined" || redirectingToLogin) return;
  redirectingToLogin = true;
  await clearSession();
  const next = nextPath ?? `${window.location.pathname}${window.location.search}`;
  const login =
    next.startsWith("/login") || next === "/"
      ? "/login"
      : `/login?next=${encodeURIComponent(safeNextPath(next))}`;
  window.location.assign(login);
}

export function getStoredUserJson(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(USER_KEY);
}

export function safeNextPath(value: string | null | undefined): string {
  if (!value || !value.startsWith("/") || value.startsWith("//") || value.startsWith("/login")) {
    return "/overview";
  }
  return value;
}
