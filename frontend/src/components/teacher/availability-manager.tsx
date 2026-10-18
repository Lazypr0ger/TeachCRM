"use client";

import { useRouter } from "next/navigation";
import { type FormEvent, useState } from "react";
import { authenticatedJson, postAuthenticated } from "@/lib/auth-api";
import { formatMoscow, fromMoscowInput } from "@/lib/lessons";
import {
  type AvailabilityException,
  type AvailabilityRule,
  parityLabel,
  weekdays,
} from "@/lib/scheduling";

export function AvailabilityManager({
  rules,
  exceptions,
}: {
  rules: AvailabilityRule[];
  exceptions: AvailabilityException[];
}) {
  const router = useRouter();
  const [error, setError] = useState("");
  const [pending, setPending] = useState(false);

  async function run(action: () => Promise<unknown>) {
    setPending(true);
    setError("");
    try {
      await action();
      router.refresh();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Не удалось сохранить доступность");
    } finally {
      setPending(false);
    }
  }

  async function addRule(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    const data = new FormData(form);
    await run(async () => {
      await postAuthenticated("/api/v1/teacher/availability-rules", {
        timezone: "Europe/Moscow",
        weekday: Number(data.get("weekday")),
        local_start_time: data.get("local_start_time"),
        local_end_time: data.get("local_end_time"),
        week_parity: data.get("week_parity"),
        cycle_anchor_date: data.get("cycle_anchor_date"),
        effective_from: data.get("effective_from"),
        effective_until: data.get("effective_until") || null,
        is_available: data.get("is_available") === "true",
      });
      form.reset();
    });
  }

  async function addException(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    const data = new FormData(form);
    await run(async () => {
      await postAuthenticated("/api/v1/teacher/availability-exceptions", {
        starts_at: fromMoscowInput(data.get("starts_at")),
        ends_at: fromMoscowInput(data.get("ends_at")),
        kind: data.get("kind"),
        private_reason: data.get("private_reason") || null,
      });
      form.reset();
    });
  }

  return <section className="availability-grid">
    <article className="management-card">
      <h2>Недельные окна</h2>
      <p className="helper-text">После добавления первого правила уроки создаются только внутри доступных окон.</p>
      <form className="availability-form" onSubmit={addRule}>
        <label>День<select name="weekday" required>{weekdays.map((day, index) => <option value={index} key={day}>{day}</option>)}</select></label>
        <label>С<input name="local_start_time" type="time" required /></label>
        <label>До<input name="local_end_time" type="time" required /></label>
        <label>Повтор<select name="week_parity"><option value="ALL">Каждую неделю</option><option value="A">Неделя A</option><option value="B">Неделя B</option></select></label>
        <label>Опорная дата A<input name="cycle_anchor_date" type="date" required /></label>
        <label>Действует с<input name="effective_from" type="date" required /></label>
        <label>Действует до<input name="effective_until" type="date" /></label>
        <label>Тип<select name="is_available"><option value="true">Доступен</option><option value="false">Недоступен</option></select></label>
        <button className="primary-button" disabled={pending} type="submit">Добавить правило</button>
      </form>
      <div className="availability-list">{rules.map((rule) => <div className="availability-row" key={rule.id}><span><strong>{weekdays[rule.weekday]}, {rule.local_start_time.slice(0, 5)}–{rule.local_end_time.slice(0, 5)}</strong><small>{rule.is_available ? "Доступен" : "Недоступен"}, {parityLabel[rule.week_parity]}</small></span><button className="danger-button" disabled={pending} type="button" onClick={() => run(() => authenticatedJson(`/api/v1/teacher/availability-rules/${rule.id}`, "DELETE"))}>Удалить</button></div>)}</div>
    </article>
    <article className="management-card">
      <h2>Разовые исключения</h2>
      <p className="helper-text">Причина видна только преподавателю.</p>
      <form className="availability-form" onSubmit={addException}>
        <label>Начало по Москве<input name="starts_at" type="datetime-local" required /></label>
        <label>Окончание по Москве<input name="ends_at" type="datetime-local" required /></label>
        <label>Тип<select name="kind"><option value="BLOCKED">Закрыть время</option><option value="AVAILABLE_OVERRIDE">Открыть время</option></select></label>
        <label>Личная причина<input name="private_reason" maxLength={2000} /></label>
        <button className="primary-button" disabled={pending} type="submit">Добавить исключение</button>
      </form>
      <div className="availability-list">{exceptions.map((item) => <div className="availability-row" key={item.id}><span><strong>{item.kind === "BLOCKED" ? "Недоступен" : "Доступен"}: {formatMoscow(item.starts_at)}–{formatMoscow(item.ends_at)}</strong>{item.private_reason ? <small>{item.private_reason}</small> : null}</span><button className="danger-button" disabled={pending} type="button" onClick={() => run(() => authenticatedJson(`/api/v1/teacher/availability-exceptions/${item.id}`, "DELETE"))}>Удалить</button></div>)}</div>
    </article>
    {error ? <p className="form-error wide-field" role="alert">{error}</p> : null}
  </section>;
}
