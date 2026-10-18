"use client";

import { useRouter } from "next/navigation";
import { type FormEvent, useState } from "react";
import { authenticatedJson, postAuthenticated } from "@/lib/auth-api";
import {
  formatMoscow,
  fromMoscowInput,
  type Lesson,
  lessonStatus,
  toMoscowInput,
} from "@/lib/lessons";

export function TeacherLessonCard({ lesson }: { lesson: Lesson }) {
  const router = useRouter();
  const [editing, setEditing] = useState(false);
  const [error, setError] = useState("");
  const [pending, setPending] = useState(false);

  async function edit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    setPending(true);
    setError("");
    try {
      await authenticatedJson<Lesson>(`/api/v1/teacher/lessons/${lesson.id}`, "PATCH", {
        version: lesson.version,
        title: data.get("title"),
        description: data.get("description") || null,
        starts_at: fromMoscowInput(data.get("starts_at")),
        ends_at: fromMoscowInput(data.get("ends_at")),
        join_url: data.get("join_url") || null,
      });
      setEditing(false);
      router.refresh();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Не удалось изменить урок");
    } finally {
      setPending(false);
    }
  }

  async function transition(action: "complete" | "cancel") {
    const question = action === "complete" ? "Отметить урок проведённым?" : "Отменить урок?";
    if (!window.confirm(question)) return;
    setPending(true);
    setError("");
    try {
      await postAuthenticated<Lesson>(`/api/v1/teacher/lessons/${lesson.id}/${action}`);
      router.refresh();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Не удалось изменить статус урока");
    } finally {
      setPending(false);
    }
  }

  return <article className="lesson-card">
    {editing ? <form className="lesson-form" onSubmit={edit}>
      <label>Тема<input name="title" required maxLength={200} defaultValue={lesson.title} /></label>
      <label>Начало по Москве<input name="starts_at" type="datetime-local" required defaultValue={toMoscowInput(lesson.starts_at)} /></label>
      <label>Окончание по Москве<input name="ends_at" type="datetime-local" required defaultValue={toMoscowInput(lesson.ends_at)} /></label>
      <label className="wide-field">Описание<textarea name="description" rows={3} defaultValue={lesson.description ?? ""} /></label>
      <label className="wide-field">Ссылка подключения<input name="join_url" type="url" pattern="https://.*" defaultValue={lesson.join_url ?? ""} /></label>
      {error ? <p className="form-error wide-field" role="alert">{error}</p> : null}
      <div className="card-actions wide-field"><button className="primary-button" disabled={pending} type="submit">Сохранить</button><button className="secondary-button" onClick={() => setEditing(false)} type="button">Отмена</button></div>
    </form> : <>
      <div className="lesson-card-heading"><div><p className="eyebrow">{lesson.student_name}{lesson.recurrence_rule_id ? " · серия" : ""}</p><h2>{lesson.title}</h2></div><span className={`status status-${lesson.status.toLowerCase()}`}>{lessonStatus[lesson.status]}</span></div>
      <p><strong>{formatMoscow(lesson.starts_at)}–{new Intl.DateTimeFormat("ru-RU", { timeZone: "Europe/Moscow", timeStyle: "short" }).format(new Date(lesson.ends_at))}</strong></p>
      {lesson.description ? <p>{lesson.description}</p> : null}
      {lesson.join_url ? <a className="text-link" href={lesson.join_url} target="_blank" rel="noreferrer">Открыть ссылку подключения</a> : <p>Ссылка подключения не указана.</p>}
      {error ? <p className="form-error" role="alert">{error}</p> : null}
      {lesson.status === "SCHEDULED" ? <div className="card-actions"><button className="secondary-button" disabled={pending} onClick={() => setEditing(true)} type="button">Изменить</button><button className="primary-button" disabled={pending} onClick={() => transition("complete")} type="button">Проведён</button><button className="danger-button" disabled={pending} onClick={() => transition("cancel")} type="button">Отменить</button></div> : null}
    </>}
  </article>;
}
