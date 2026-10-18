"use client";

import { useRouter } from "next/navigation";
import { type FormEvent, useState } from "react";
import { authenticatedJson, postAuthenticated } from "@/lib/auth-api";
import type { RecurrenceRule } from "@/lib/scheduling";
import { weekdays } from "@/lib/scheduling";
import type { Student } from "@/lib/students";

export function RecurrenceManager({
  rules,
  students,
}: {
  rules: RecurrenceRule[];
  students: Student[];
}) {
  const router = useRouter();
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [pending, setPending] = useState(false);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    const data = new FormData(form);
    const startsOn = String(data.get("starts_on"));
    setPending(true);
    setError("");
    setMessage("");
    try {
      const result = await postAuthenticated<RecurrenceRule>(
        "/api/v1/teacher/recurrence-rules",
        {
          student_id: data.get("student_id"),
          title: data.get("title"),
          description: data.get("description") || null,
          join_url: data.get("join_url") || null,
          local_time: data.get("local_time"),
          duration_minutes: Number(data.get("duration_minutes")),
          timezone: "Europe/Moscow",
          by_weekday: new Date(`${startsOn}T12:00:00+03:00`).getUTCDay() === 0
            ? 6
            : new Date(`${startsOn}T12:00:00+03:00`).getUTCDay() - 1,
          interval_weeks: Number(data.get("interval_weeks")),
          starts_on: startsOn,
          ends_on: data.get("ends_on") || null,
          count_limit: data.get("ends_on") || !data.get("count_limit")
            ? null
            : Number(data.get("count_limit")),
        },
      );
      form.reset();
      setMessage(`Серия создана, добавлено уроков: ${result.materialized_count}`);
      router.refresh();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Не удалось создать серию");
    } finally {
      setPending(false);
    }
  }

  async function deactivate(rule: RecurrenceRule) {
    if (!window.confirm("Остановить серию и отменить её будущие уроки?")) return;
    setPending(true);
    setError("");
    try {
      await authenticatedJson(`/api/v1/teacher/recurrence-rules/${rule.id}`, "DELETE");
      router.refresh();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Не удалось остановить серию");
    } finally {
      setPending(false);
    }
  }

  return <section className="management-card recurrence-card">
    <h2>Повторяющиеся уроки</h2>
    <p className="helper-text">Укажите дату первого занятия. Интервал «через неделю» создаёт занятия раз в две недели.</p>
    {students.length ? <form className="lesson-form" onSubmit={submit}>
      <label>Ученик<select name="student_id" required>{students.map((student) => <option value={student.id} key={student.id}>{student.last_name} {student.first_name}</option>)}</select></label>
      <label>Тема<input name="title" required maxLength={200} /></label>
      <label>Первое занятие<input name="starts_on" type="date" required /></label>
      <label>Время по Москве<input name="local_time" type="time" required /></label>
      <label>Длительность, минут<input name="duration_minutes" type="number" min={5} max={480} defaultValue={60} required /></label>
      <label>Период<select name="interval_weeks"><option value="1">Каждую неделю</option><option value="2">Через неделю</option></select></label>
      <label>Дата окончания<input name="ends_on" type="date" /></label>
      <label>Или число занятий<input name="count_limit" type="number" min={1} max={520} /></label>
      <label className="wide-field">Описание<textarea name="description" maxLength={10000} rows={2} /></label>
      <label className="wide-field">Ссылка подключения HTTPS<input name="join_url" type="url" pattern="https://.*" /></label>
      <button className="primary-button" disabled={pending} type="submit">Создать серию</button>
    </form> : <p>Сначала создайте ученика.</p>}
    {error ? <p className="form-error" role="alert">{error}</p> : null}
    {message ? <p className="form-success" role="status">{message}</p> : null}
    <div className="availability-list">{rules.map((rule) => <div className="availability-row" key={rule.id}><span><strong>{rule.student_name}: {rule.title}</strong><small>{weekdays[rule.by_weekday]}, {rule.local_time.slice(0, 5)}, {rule.interval_weeks === 1 ? "каждую неделю" : "через неделю"}; с {rule.starts_on}{rule.ends_on ? ` до ${rule.ends_on}` : rule.count_limit ? `, ${rule.count_limit} занятий` : ""}</small><small>{rule.active ? "Активна" : "Остановлена"}</small></span>{rule.active ? <button className="danger-button" disabled={pending} type="button" onClick={() => deactivate(rule)}>Остановить</button> : null}</div>)}</div>
  </section>;
}
