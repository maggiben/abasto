const API_BASE =
  typeof window !== "undefined"
    ? (process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000")
    : (process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000");

export function getApiBase(): string {
  return API_BASE.replace(/\/$/, "");
}

export class ApiError extends Error {
  constructor(
    message: string,
    public status: number,
    public body?: unknown,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

export async function apiFetch<T>(
  path: string,
  options: RequestInit & { token?: string | null } = {},
): Promise<T> {
  const { token, headers: hdrs, ...rest } = options;
  const headers = new Headers(hdrs);
  if (!headers.has("Content-Type") && rest.body && !(rest.body instanceof FormData)) {
    headers.set("Content-Type", "application/json");
  }
  if (token) {
    headers.set("Authorization", `Bearer ${token}`);
  }
  const res = await fetch(`${getApiBase()}${path}`, {
    ...rest,
    headers,
  });
  const text = await res.text();
  let data: unknown = undefined;
  if (text) {
    try {
      data = JSON.parse(text) as unknown;
    } catch {
      data = text;
    }
  }
  if (!res.ok) {
    const detail = typeof data === "object" && data !== null && "detail" in data
      ? (data as { detail: unknown }).detail
      : undefined;
    let msg = res.statusText;
    if (typeof detail === "string") msg = detail;
    else if (detail !== undefined) msg = JSON.stringify(detail);
    throw new ApiError(msg || "Request failed", res.status, data);
  }
  return data as T;
}
