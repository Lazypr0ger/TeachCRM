"use client";

import { type FormEvent, useState } from "react";
import { postJson } from "@/lib/auth-api";
import { fromMoscowInput } from "@/lib/lessons";

export function TrialRequestForm() {
  const [pending, setPending] = useState(false);
  const [error, setError] = useState("");
  const [sent, setSent] = useState(false);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    const data = new FormData(form);
    setPending(true);
    setError("");
    try {
      await postJson<{ message: string }>("/api/v1/public/trial-requests", {
        name: data.get("name"),
        grade: Number(data.get("grade")),
        goal: data.get("goal") || null,
        preferred_start: data.get("preferred_start") ? fromMoscowInput(data.get("preferred_start")) : null,
        preferred_end: data.get("preferred_end") ? fromMoscowInput(data.get("preferred_end")) : null,
        comment: data.get("comment") || null,
        website: data.get("website") || "",
      });
      form.reset();
      setSent(true);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Не удалось отправить заявку");
    } finally {
      setPending(false);
    }
  }

  return <section className="public-trial" id="trial">
    <div><p className="eyebrow">Пробное занятие</p><h2>Оставить заявку</h2><p className="helper-text">Укажите только ФИО и класс. Телефон, email и платёжные данные не запрашиваются.</p></div>
    {sent ? <div className="management-card" role="status"><h3>Заявка принята</h3><p>Преподаватель увидит её в CRM.</p></div> : <form className="lesson-form management-card" onSubmit={submit}>
      <label className="wide-field">ФИО<input name="name" required minLength={3} maxLength={300} autoComplete="name" placeholder="Иванов Иван Иванович" /></label>
      <label>Класс<input name="grade" required type="number" min={1} max={11} /></label>
      <label>Цель занятия<input name="goal" maxLength={1000} /></label>
      <label>Желаемое начало по Москве<input name="preferred_start" type="datetime-local" /></label>
      <label>Желаемое окончание по Москве<input name="preferred_end" type="datetime-local" /></label>
      <label className="wide-field">Комментарий<textarea name="comment" rows={3} maxLength={2000} /></label>
      <label className="honeypot" aria-hidden="true">Сайт<input name="website" tabIndex={-1} autoComplete="off" /></label>
      {error ? <p className="form-error wide-field" role="alert">{error}</p> : null}
      <button className="primary-button wide-field" disabled={pending} type="submit">{pending ? "Отправляем…" : "Отправить заявку"}</button>
    </form>}
  </section>;
}
