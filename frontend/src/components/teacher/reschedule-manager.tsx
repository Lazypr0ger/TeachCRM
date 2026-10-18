"use client";

import { useRouter } from "next/navigation";
import { type FormEvent, useState } from "react";
import { postAuthenticated } from "@/lib/auth-api";
import { formatMoscow, fromMoscowInput } from "@/lib/lessons";
import {
  type RescheduleRequest,
  rescheduleStatus,
} from "@/lib/scheduling";

export function TeacherRescheduleManager({ requests }: { requests: RescheduleRequest[] }) {
  const router = useRouter();
  const [error, setError] = useState("");
  const [pending, setPending] = useState(false);

  async function action(id: string, name: "accept" | "reject", payload: unknown = {}) {
    setPending(true);
    setError("");
    try {
      await postAuthenticated(`/api/v1/teacher/reschedule-requests/${id}/${name}`, payload);
      router.refresh();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Не удалось обработать запрос");
    } finally {
      setPending(false);
    }
  }

  async function counter(event: FormEvent<HTMLFormElement>, id: string) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    setPending(true);
    setError("");
    try {
      await postAuthenticated(`/api/v1/teacher/reschedule-requests/${id}/counter`, {
        counter_starts_at: fromMoscowInput(data.get("starts_at")),
        counter_ends_at: fromMoscowInput(data.get("ends_at")),
        response_note: data.get("response_note") || null,
      });
      router.refresh();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Не удалось предложить время");
    } finally {
      setPending(false);
    }
  }

  return <section className="management-card recurrence-card">
    <h2>Запросы переноса</h2>
    {error ? <p className="form-error" role="alert">{error}</p> : null}
    <div className="availability-list">{requests.length ? requests.map((item) => <article className="request-card" key={item.id}><div><p className="eyebrow">{item.student_name}</p><strong>{item.lesson_title}</strong><p>Текущее время: {formatMoscow(item.original_starts_at)}</p><p>Ученик предлагает: {formatMoscow(item.proposed_starts_at)}</p>{item.reason ? <p>Причина: {item.reason}</p> : null}{item.counter_starts_at ? <p>Встречный вариант: {formatMoscow(item.counter_starts_at)}</p> : null}{item.response_note ? <p>Ответ: {item.response_note}</p> : null}<span className="status status-scheduled">{rescheduleStatus[item.status]}</span></div>{item.status === "PENDING" ? <div><div className="card-actions"><button className="primary-button" disabled={pending} type="button" onClick={() => action(item.id, "accept")}>Принять перенос</button><button className="danger-button" disabled={pending} type="button" onClick={() => action(item.id, "reject", { response_note: "Запрос отклонён преподавателем" })}>Отклонить</button></div><form className="availability-form counter-form" onSubmit={(event) => counter(event, item.id)}><label>Другое начало<input name="starts_at" type="datetime-local" required /></label><label>Другое окончание<input name="ends_at" type="datetime-local" required /></label><label>Комментарий<input name="response_note" maxLength={2000} /></label><button className="secondary-button" disabled={pending} type="submit">Предложить другое время</button></form></div> : null}</article>) : <p>Запросов переноса пока нет.</p>}</div>
  </section>;
}
