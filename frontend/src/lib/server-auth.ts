import { headers } from "next/headers";
import { redirect } from "next/navigation";
import type { AuthUser } from "./auth-api";

function apiRequestHeaders(incomingHeaders: Headers): HeadersInit {
  return { cookie: incomingHeaders.get("cookie") ?? "" };
}

export async function requireRole(role: AuthUser["role"]): Promise<AuthUser> {
  const incomingHeaders = await headers();
  const apiUrl = process.env.API_INTERNAL_URL ?? "http://127.0.0.1:8000";
  const response = await fetch(`${apiUrl}/api/v1/auth/me`, {
    headers: apiRequestHeaders(incomingHeaders),
    cache: "no-store",
  });
  if (response.status === 401) redirect("/login");
  if (!response.ok) throw new Error("Не удалось проверить сессию");
  const user = (await response.json()) as AuthUser;
  if (user.role !== role) redirect(user.role === "TEACHER" ? "/teacher" : "/student");
  return user;
}

export async function serverGet<T>(path: string): Promise<T> {
  const incomingHeaders = await headers();
  const apiUrl = process.env.API_INTERNAL_URL ?? "http://127.0.0.1:8000";
  const response = await fetch(`${apiUrl}${path}`, {
    headers: apiRequestHeaders(incomingHeaders),
    cache: "no-store",
  });
  if (response.status === 401) redirect("/login");
  if (response.status === 403) redirect("/student");
  if (response.status === 404) redirect("/teacher/students");
  if (!response.ok) throw new Error("Не удалось загрузить данные")
  return response.json() as Promise<T>;
}
