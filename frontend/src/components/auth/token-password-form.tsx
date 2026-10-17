"use client";

import { useState, type FormEvent } from "react";
import { postJson } from "@/lib/auth-api";

type Props = {
  endpoint: "/api/v1/auth/activate" | "/api/v1/auth/reset-password";
  token: string;
  title: string;
  description: string;
};

export function TokenPasswordForm({ endpoint, token, title, description }: Props) {
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [pending, setPending] = useState(false);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    setPending(true);
    try {
      const result = await postJson<{ message: string }>(endpoint, {
        token,
        new_password: password,
      });
      setMessage(result.message);
      setPassword("");
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Не удалось сохранить пароль");
    } finally {
      setPending(false);
    }
  }

  return (
    <main className="auth-shell">
      <section className="auth-card">
        <h1>{title}</h1>
        <p>{description}</p>
        {!token ? <p className="form-error">В ссылке отсутствует токен.</p> : null}
        <form className="auth-form" onSubmit={submit}>
          <label>
            Новый пароль
            <input
              type="password"
              autoComplete="new-password"
              minLength={12}
              maxLength={128}
              required
              value={password}
              onChange={(event) => setPassword(event.target.value)}
            />
          </label>
          {error ? <p className="form-error" role="alert">{error}</p> : null}
          {message ? <p className="form-success" role="status">{message}</p> : null}
          <button className="primary-button" disabled={pending || !token} type="submit">
            {pending ? "Сохраняем…" : "Сохранить пароль"}
          </button>
        </form>
        <p><a className="text-link" href="/login">Перейти ко входу</a></p>
      </section>
    </main>
  );
}
