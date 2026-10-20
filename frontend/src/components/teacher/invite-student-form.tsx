"use client";

import { useRouter } from "next/navigation";
import { type FormEvent, useState } from "react";
import { postAuthenticated } from "@/lib/auth-api";

type Invitation = {
  login: string;
  activation_url: string;
  expires_at: string;
};

export function InviteStudentForm() {
  const router = useRouter();
  const [result, setResult] = useState<Invitation | null>(null);
  const [error, setError] = useState("");
  const [pending, setPending] = useState(false);
  const [open, setOpen] = useState(false);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    setPending(true);
    const form = event.currentTarget;
    const data = new FormData(form);
    try {
      const invitation = await postAuthenticated<Invitation>("/api/v1/teacher/students", {
        first_name: data.get("first_name"),
        last_name: data.get("last_name"),
        patronymic: data.get("patronymic") || null,
        grade: data.get("grade") ? Number(data.get("grade")) : null,
        login: data.get("login") || null,
      });
      setResult(invitation);
      form.reset();
      router.refresh();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Не удалось создать приглашение");
    } finally {
      setPending(false);
    }
  }

  return (
    <><button className="primary-button" type="button" onClick={() => setOpen(true)}>Добавить ученика</button>
    {open ? <div className="modal-backdrop">
    <section className="modal-card" role="dialog" aria-modal="true" aria-labelledby="invite-title">
      <div className="section-heading"><h2 id="invite-title">Пригласить ученика</h2><button className="secondary-button compact-button" type="button" onClick={() => setOpen(false)} aria-label="Закрыть">Закрыть</button></div>
      <p>Ссылка показывается один раз. Передайте её ученику вручную.</p>
      <form className="auth-form" onSubmit={submit}>
        <label>Фамилия<input name="last_name" required maxLength={100} /></label>
        <label>Имя<input name="first_name" required maxLength={100} /></label>
        <label>Отчество<input name="patronymic" maxLength={100} /></label>
        <label>Класс<input name="grade" type="number" min={1} max={11} /></label>
        <label>Логин (необязательно)<input name="login" minLength={3} maxLength={120} /></label>
        {error ? <p className="form-error" role="alert">{error}</p> : null}
        <button className="primary-button" disabled={pending} type="submit">
          {pending ? "Создаём…" : "Создать приглашение"}
        </button>
      </form>
      {result ? <div className="invitation-result" role="status">
        <strong>Логин: {result.login}</strong>
        <a className="text-link" href={result.activation_url}>{result.activation_url}</a>
        <span>Действует до {new Date(result.expires_at).toLocaleString("ru-RU")}</span>
      </div> : null}
    </section></div> : null}</>
  );
}
