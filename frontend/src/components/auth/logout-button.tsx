"use client";

import { postAuthenticated } from "@/lib/auth-api";

export function LogoutButton() {
  async function logout() {
    await postAuthenticated("/api/v1/auth/logout");
    window.location.assign("/login");
  }
  return <button className="primary-button" onClick={logout} type="button">Выйти</button>;
}
