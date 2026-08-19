import { getOrgId, getToken, redirectToLogin } from "@/lib/session";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
    public detail?: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

type RequestOptions = Omit<RequestInit, "body"> & {
  body?: unknown;
  orgId?: string | null;
};

export function errorMessage(error: unknown): string {
  if (error instanceof ApiError) return error.message;
  if (error instanceof Error) {
    if (error.message === "Failed to fetch" || error.name === "TypeError") {
      return "No se pudo conectar con el servidor. Inténtalo de nuevo en unos segundos.";
    }
    return error.message;
  }
  return "Ha ocurrido un error inesperado.";
}

export function errorDetail(error: unknown): string {
  if (error instanceof ApiError) return error.detail || error.message;
  if (error instanceof Error) return [error.name, error.message, error.stack].filter(Boolean).join("\n");
  return String(error);
}

export async function apiFetch<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const headers = new Headers(options.headers);
  const isAuthPath = path.startsWith("/api/v1/auth/login") || path.startsWith("/api/v1/auth/register");
  const token = isAuthPath ? null : getToken();
  const orgId = isAuthPath ? null : (options.orgId ?? getOrgId());

  if (!(options.body instanceof FormData)) {
    headers.set("Content-Type", "application/json");
  }
  if (token) headers.set("Authorization", `Bearer ${token}`);
  if (orgId) headers.set("X-Organization-Id", orgId);

  let response: Response;
  try {
    response = await fetch(`${API_URL}${path}`, {
      ...options,
      cache: "no-store",
      headers,
      body:
        options.body instanceof FormData
          ? options.body
          : options.body !== undefined
            ? JSON.stringify(options.body)
            : undefined,
    });
  } catch (err) {
    const raw = err instanceof Error ? err.message : String(err);
    throw new ApiError(
      0,
      "No se pudo conectar con el servidor. Inténtalo de nuevo en unos segundos.",
      raw,
    );
  }

  if (!response.ok) {
    let detail = response.statusText;
    try {
      const data = (await response.json()) as { detail?: unknown };
      if (typeof data.detail === "string") {
        detail = data.detail;
      } else if (Array.isArray(data.detail)) {
        detail = data.detail
          .map((item) => (typeof item === "object" && item && "msg" in item ? String(item.msg) : String(item)))
          .join(". ");
      }
    } catch {
      /* ignore */
    }
    if (
      !isAuthPath &&
      (response.status === 401 || detail === "Invalid token") &&
      (!token || getToken() === token)
    ) {
      void redirectToLogin();
    }
    const message =
      response.status >= 500
        ? "El servidor no pudo completar la solicitud. Puedes enviar un informe al equipo técnico."
        : detail;
    throw new ApiError(response.status, message, detail);
  }

  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

export async function reportClientError(input: {
  path?: string;
  message: string;
  detail?: string;
}): Promise<boolean> {
  try {
    await apiFetch("/api/v1/support/error-reports", {
      method: "POST",
      body: {
        path: input.path ?? (typeof window !== "undefined" ? window.location.pathname : "/"),
        message: input.message.slice(0, 2000),
        detail: input.detail?.slice(0, 8000),
        user_agent: typeof navigator !== "undefined" ? navigator.userAgent : null,
      },
    });
    return true;
  } catch {
    return false;
  }
}

export async function fetchCover(documentId: string): Promise<Blob | null> {
  const headers = new Headers();
  const token = getToken();
  const orgId = getOrgId();
  if (token) headers.set("Authorization", `Bearer ${token}`);
  if (orgId) headers.set("X-Organization-Id", orgId);

  const urls = [
    `/api/documents/${documentId}/cover`,
    `${API_URL}/api/v1/documents/${documentId}/cover`,
  ];
  for (const url of urls) {
    try {
      const response = await fetch(url, { headers });
      if (response.status === 404 || response.status === 204) {
        const type = response.headers.get("content-type") ?? "";
        if (url.startsWith("http") || type.startsWith("image/")) return null;
        continue;
      }
      if (!response.ok) continue;
      const blob = await response.blob();
      if (!blob.size || blob.type.includes("json")) return null;
      return blob;
    } catch {
      continue;
    }
  }
  return null;
}
