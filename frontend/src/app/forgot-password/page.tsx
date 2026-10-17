"use client";

import { type FormEvent, useState } from "react";
import { postJson } from "@/lib/auth-api";

export default function ForgotPasswordPage() {
  const [login, setLogin] = useState("");
  const [message, setMessage] = useState("");
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const result = await postJson<{ message: string }>("/api/v1/auth/request-password-reset", { login });
    setMessage(result.message);
  }
  return (
    <main className="auth-shell"><section className="auth-card">
      <h1>Восстановление пароля</h1>
      <p>В локальной версии одноразовую ссылку передаёт преподаватель вручную.</p>
      <form className="auth-form" onSubmit={submit}>
        <label>Логин<input required value={login} onChange={(e) => setLogin(e.target.value)} /></label>
        {message ? <p className="form-success" role="status">{message}</p> : null}
        <button className="primary-button" type="submit">Отправить запрос</button>
      </form>
    </section></main>
  );
}
