"use client";

import { type FormEvent, useState } from "react";
import type { AuthUser } from "@/lib/auth-api";
import { postJson } from "@/lib/auth-api";

export default function LoginPage() {
  const [login, setLogin] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [pending, setPending] = useState(false);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    setPending(true);
    try {
      const result = await postJson<{ user: AuthUser; csrf_token: string }>(
        "/api/v1/auth/login",
        { login, password },
      );
      window.location.assign(result.user.role === "TEACHER" ? "/teacher" : "/student");
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Не удалось войти");
      setPending(false);
    }
  }

  return (
    <main className="auth-shell">
      <section className="auth-card">
        <h1>Вход в Tutor CRM</h1>
        <p>Используйте логин и пароль из приглашения преподавателя.</p>
        <form className="auth-form" onSubmit={submit}>
          <label>Логин<input autoComplete="username" required value={login} onChange={(e) => setLogin(e.target.value)} /></label>
          <label>Пароль<input type="password" autoComplete="current-password" required value={password} onChange={(e) => setPassword(e.target.value)} /></label>
          {error ? <p className="form-error" role="alert">{error}</p> : null}
          <button className="primary-button" disabled={pending} type="submit">{pending ? "Входим…" : "Войти"}</button>
        </form>
        <p><a className="text-link" href="/forgot-password">Не помню пароль</a></p>
      </section>
    </main>
  );
}
