"use client";

import { useRouter } from "next/navigation";
import { type FormEvent, useState } from "react";
import { authenticatedJson, postAuthenticated } from "@/lib/auth-api";
import type { Student } from "@/lib/students";

type Invitation = { login: string; activation_url: string; expires_at: string };

export function StudentCardForm({ student }: { student: Student }) {
  const router = useRouter();
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [pending, setPending] = useState(false);
  const [invitation, setInvitation] = useState<Invitation | null>(null);

  async function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    setPending(true);
    setError("");
    setMessage("");
    try {
      await authenticatedJson(`/api/v1/teacher/students/${student.id}`, "PATCH", {
        first_name: data.get("first_name"),
        last_name: data.get("last_name"),
        patronymic: data.get("patronymic") || null,
        grade: data.get("grade") ? Number(data.get("grade")) : null,
      });
      setMessage("Карточка сохранена");
      router.refresh();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Не удалось сохранить карточку");
    } finally {
      setPending(false);
    }
  }

  async function renewInvitation() {
    setPending(true);
    setError("");
    try {
      const result = await postAuthenticated<Invitation>(
        `/api/v1/teacher/students/${student.id}/invite`,
      );
      setInvitation(result);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Не удалось создать приглашение");
    } finally {
      setPending(false);
    }
  }

  async function suspend() {
    if (!window.confirm("Заблокировать ученика и завершить все его сессии?")) return;
    setPending(true);
    setError("");
    try {
      await postAuthenticated(`/api/v1/teacher/students/${student.id}/suspend`);
      setMessage("Ученик заблокирован");
      router.refresh();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Не удалось заблокировать ученика");
    } finally {
      setPending(false);
    }
  }

  return <section className="management-card">
    <h2>Основные данные</h2>
    <form className="auth-form" onSubmit={save}>
      <label>Фамилия<input name="last_name" required maxLength={100} defaultValue={student.last_name} /></label>
      <label>Имя<input name="first_name" required maxLength={100} defaultValue={student.first_name} /></label>
      <label>Отчество<input name="patronymic" maxLength={100} defaultValue={student.patronymic ?? ""} /></label>
      <label>Класс<input name="grade" type="number" min={1} max={11} defaultValue={student.grade ?? ""} /></label>
      {error ? <p className="form-error" role="alert">{error}</p> : null}
      {message ? <p className="form-success" role="status">{message}</p> : null}
      <button className="primary-button" disabled={pending} type="submit">Сохранить</button>
    </form>
    <div className="card-actions">
      {student.status === "INVITED" ? <button className="secondary-button" disabled={pending} onClick={renewInvitation} type="button">Новая ссылка приглашения</button> : null}
      {student.status !== "SUSPENDED" ? <button className="danger-button" disabled={pending} onClick={suspend} type="button">Заблокировать ученика</button> : null}
    </div>
    {invitation ? <div className="invitation-result" role="status">
      <strong>Логин: {invitation.login}</strong>
      <a className="text-link" href={invitation.activation_url}>{invitation.activation_url}</a>
      <span>Действует до {new Date(invitation.expires_at).toLocaleString("ru-RU")}</span>
    </div> : null}
  </section>;
}
