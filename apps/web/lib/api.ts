import { tStored } from "@/lib/i18n/stored";
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
      return tStored("error.network");
    }
    return error.message;
  }
  return tStored("error.unexpected");
}

export function errorDetail(error: unknown): string {
  if (error instanceof ApiError) return error.detail || error.message;
  if (error instanceof Error) return [error.name, error.message, error.stack].filter(Boolean).join("\n");
  return String(error);
}

export async function apiFetch<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const headers = new Headers(options.headers);
  const isAuthPath =
    path.startsWith("/api/v1/auth/login") ||
    path.startsWith("/api/v1/auth/register") ||
    path.startsWith("/api/v1/auth/recovery");
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
      tStored("error.network"),
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
        ? tStored("error.server")
        : detail;
    throw new ApiError(response.status, message, detail);
  }

  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

export async function apiUpload<T>(
  path: string,
  body: FormData,
  onProgress?: (percent: number) => void,
): Promise<T> {
  const token = getToken();
  const orgId = getOrgId();

  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open("POST", `${API_URL}${path}`);
    if (token) xhr.setRequestHeader("Authorization", `Bearer ${token}`);
    if (orgId) xhr.setRequestHeader("X-Organization-Id", orgId);

    xhr.upload.onprogress = (event) => {
      if (!event.lengthComputable || event.total <= 0) return;
      onProgress?.(Math.max(0, Math.min(100, Math.round((event.loaded / event.total) * 100))));
    };
    xhr.upload.onload = () => onProgress?.(100);

    xhr.onload = () => {
      const status = xhr.status;
      const raw = xhr.responseText || "";
      if (status === 401) {
        void redirectToLogin();
      }
      if (status < 200 || status >= 300) {
        let detail = xhr.statusText;
        try {
          const data = JSON.parse(raw) as { detail?: unknown };
          if (typeof data.detail === "string") {
            detail = data.detail;
          } else if (Array.isArray(data.detail)) {
            detail = data.detail
              .map((item) =>
                typeof item === "object" && item && "msg" in item ? String(item.msg) : String(item),
              )
              .join(". ");
          }
        } catch {
          if (raw) detail = raw.slice(0, 400);
        }
        const message = status >= 500 ? tStored("error.server") : detail;
        reject(new ApiError(status, message, detail));
        return;
      }
      if (status === 204) {
        resolve(undefined as T);
        return;
      }
      try {
        resolve(JSON.parse(raw) as T);
      } catch {
        reject(new ApiError(status, tStored("error.unexpected"), raw));
      }
    };

    xhr.onerror = () => {
      reject(new ApiError(0, tStored("error.network")));
    };
    xhr.onabort = () => {
      reject(new ApiError(0, tStored("error.network")));
    };
    xhr.send(body);
  });
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
