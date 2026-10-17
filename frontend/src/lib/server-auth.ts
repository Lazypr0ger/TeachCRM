import { headers } from "next/headers";
import { redirect } from "next/navigation";
import type { AuthUser } from "./auth-api";

export async function requireRole(role: AuthUser["role"]): Promise<AuthUser> {
  const incomingHeaders = await headers();
  const apiUrl = process.env.API_INTERNAL_URL ?? "http://127.0.0.1:8000";
  const response = await fetch(`${apiUrl}/api/v1/auth/me`, {
    headers: { cookie: incomingHeaders.get("cookie") ?? "" },
    cache: "no-store",
  });
  if (response.status === 401) redirect("/login");
  if (!response.ok) throw new Error("Не удалось проверить сессию");
  const user = (await response.json()) as AuthUser;
  if (user.role !== role) redirect(user.role === "TEACHER" ? "/teacher" : "/student");
  return user;
}
