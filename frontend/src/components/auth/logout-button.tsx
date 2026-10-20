"use client";

import { postAuthenticated } from "@/lib/auth-api";

export function LogoutButton({ className = "primary-button" }: { className?: string }) {
  async function logout() {
    await postAuthenticated("/api/v1/auth/logout");
    window.location.assign("/login");
  }
  return <button className={className} onClick={logout} type="button">Выйти</button>;
}
