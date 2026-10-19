export type AuthUser = {
  id: string;
  role: "STUDENT" | "TEACHER";
  login: string;
  status: string;
};

type ApiError = { detail?: string };

export async function postJson<T>(url: string, payload: unknown): Promise<T> {
  const response = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  const result = (await response.json()) as T & ApiError;
  if (!response.ok) {
    throw new Error(result.detail ?? "Не удалось выполнить запрос");
  }
  return result;
}

function csrfToken(): string {
  const match = document.cookie.match(/(?:^|; )tutorcrm_csrf=([^;]*)/);
  return match ? decodeURIComponent(match[1]) : "";
}

export async function uploadAuthenticated<T>(url: string, file: File): Promise<T> {
  const body = new FormData();
  body.set("file", file);
  const response = await fetch(url, {
    method: "POST",
    headers: { "X-CSRF-Token": csrfToken() },
    body,
  });
  if (response.status === 204) return undefined as T;
  const result = (await response.json()) as T & ApiError;
  if (!response.ok) throw new Error(result.detail ?? "Не удалось загрузить файл");
  return result;
}

export async function postAuthenticated<T>(url: string, payload: unknown = {}): Promise<T> {
  return authenticatedJson<T>(url, "POST", payload);
}

export async function authenticatedJson<T>(
  url: string,
  method: "POST" | "PATCH" | "DELETE",
  payload?: unknown,
): Promise<T> {
  const response = await fetch(url, {
    method,
    headers: { "Content-Type": "application/json", "X-CSRF-Token": csrfToken() },
    body: payload === undefined ? undefined : JSON.stringify(payload),
  });
  if (response.status === 204) return undefined as T;
  const result = (await response.json()) as T & ApiError;
  if (!response.ok) throw new Error(result.detail ?? "Не удалось выполнить запрос");
  return result;
}
