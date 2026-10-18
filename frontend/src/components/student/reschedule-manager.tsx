"use client";

import { useRouter } from "next/navigation";
import { type FormEvent, useState } from "react";
import { postAuthenticated } from "@/lib/auth-api";
import { formatMoscow, fromMoscowInput, type Lesson } from "@/lib/lessons";
import {
  type RescheduleRequest,
  rescheduleStatus,
} from "@/lib/scheduling";

export function StudentRescheduleManager({
  lessons,
  requests,
}: {
  lessons: Lesson[];
  requests: RescheduleRequest[];
}) {
  const router = useRouter();
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [pending, setPending] = useState(false);
  const activeLessonIds = new Set(
    requests
      .filter((item) => item.status === "PENDING" || item.status === "COUNTER_OFFER")
      .map((item) => item.lesson_id),
  );
  const availableLessons = lessons.filter(
    (lesson) => lesson.status === "SCHEDULED" && !activeLessonIds.has(lesson.id),
  );

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    const data = new FormData(form);
    setPending(true);
    setError("");
    setMessage("");
    try {
      await postAuthenticated(`/api/v1/student/lessons/${data.get("lesson_id")}/reschedule-requests`, {
        proposed_starts_at: fromMoscowInput(data.get("starts_at")),
        proposed_ends_at: fromMoscowInput(data.get("ends_at")),
        reason: data.get("reason") || null,
      });
      form.reset();
      setMessage("Запрос отправлен преподавателю");
      router.refresh();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Не удалось отправить запрос");
    } finally {
      setPending(false);
    }
  }

  async function transition(id: string, action: "accept-counter" | "cancel") {
    setPending(true);
    setError("");
    try {
      await postAuthenticated(`/api/v1/student/reschedule-requests/${id}/${action}`);
      router.refresh();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Не удалось изменить запрос");
    } finally {
      setPending(false);
    }
  }

  return <section className="management-card recurrence-card">
    <h2>Запросить перенос</h2>
    {availableLessons.length ? <form className="lesson-form" onSubmit={submit}>
      <label className="wide-field">Урок<select name="lesson_id" required>{availableLessons.map((lesson) => <option value={lesson.id} key={lesson.id}>{formatMoscow(lesson.starts_at)} · {lesson.title}</option>)}</select></label>
      <label>Желаемое начало<input name="starts_at" type="datetime-local" required /></label>
      <label>Желаемое окончание<input name="ends_at" type="datetime-local" required /></label>
      <label className="wide-field">Причина<textarea name="reason" rows={2} maxLength={2000} /></label>
      <button className="primary-button" disabled={pending} type="submit">Отправить запрос</button>
    </form> : <p className="helper-text">Нет уроков без активного запроса переноса.</p>}
    {error ? <p className="form-error" role="alert">{error}</p> : null}
    {message ? <p className="form-success" role="status">{message}</p> : null}
    <div className="availability-list">{requests.map((item) => <div className="request-card" key={item.id}><div><strong>{item.lesson_title}</strong><p>Было: {formatMoscow(item.original_starts_at)}</p><p>Предложено: {formatMoscow(item.proposed_starts_at)}</p>{item.counter_starts_at ? <p>Вариант преподавателя: {formatMoscow(item.counter_starts_at)}</p> : null}{item.response_note ? <p>{item.response_note}</p> : null}<span className="status status-scheduled">{rescheduleStatus[item.status]}</span></div>{item.status === "COUNTER_OFFER" ? <div className="card-actions"><button className="primary-button" disabled={pending} type="button" onClick={() => transition(item.id, "accept-counter")}>Принять вариант</button><button className="danger-button" disabled={pending} type="button" onClick={() => transition(item.id, "cancel")}>Отказаться</button></div> : item.status === "PENDING" ? <button className="danger-button" disabled={pending} type="button" onClick={() => transition(item.id, "cancel")}>Отменить запрос</button> : null}</div>)}</div>
  </section>;
}
