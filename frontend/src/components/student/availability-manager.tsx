"use client";

import { useRouter } from "next/navigation";
import { type FormEvent, useState } from "react";
import { authenticatedJson, postAuthenticated } from "@/lib/auth-api";
import { formatMoscow, fromMoscowInput } from "@/lib/lessons";
import type { StudentAvailability } from "@/lib/scheduling";

export function StudentAvailabilityManager({ items }: { items: StudentAvailability[] }) {
  const router = useRouter();
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [pending, setPending] = useState(false);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    const data = new FormData(form);
    setPending(true);
    setError("");
    setMessage("");
    try {
      const result = await postAuthenticated<StudentAvailability>("/api/v1/student/availability", {
        starts_at: fromMoscowInput(data.get("starts_at")),
        ends_at: fromMoscowInput(data.get("ends_at")),
        state: data.get("state"),
      });
      setMessage(result.conflicts_with_lesson ? "Отметка сохранена. Она пересекается с запланированным уроком — урок не отменён." : "Отметка сохранена.");
      form.reset();
      router.refresh();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Не удалось сохранить отметку");
    } finally {
      setPending(false);
    }
  }

  async function remove(id: string) {
    setPending(true);
    setError("");
    try {
      await authenticatedJson(`/api/v1/student/availability/${id}`, "DELETE");
      router.refresh();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Не удалось удалить отметку");
    } finally {
      setPending(false);
    }
  }

  return <section className="management-card">
    <h2>Моя доступность</h2>
    <p className="helper-text">Отметка «занят» предупредит преподавателя, но не отменит уже созданный урок.</p>
    <form className="availability-form" onSubmit={submit}>
      <label>Начало по Москве<input name="starts_at" type="datetime-local" required /></label>
      <label>Окончание по Москве<input name="ends_at" type="datetime-local" required /></label>
      <label>Состояние<select name="state"><option value="BUSY">Занят</option><option value="AVAILABLE">Свободен</option></select></label>
      <button className="primary-button" disabled={pending} type="submit">Добавить</button>
    </form>
    {error ? <p className="form-error" role="alert">{error}</p> : null}
    {message ? <p className="form-success" role="status">{message}</p> : null}
    <div className="availability-list">{items.map((item) => <div className="availability-row" key={item.id}><span><strong>{item.state === "BUSY" ? "Занят" : "Свободен"}: {formatMoscow(item.starts_at)}–{formatMoscow(item.ends_at)}</strong>{item.conflicts_with_lesson ? <small className="warning-text">Пересекается с уроком</small> : null}</span><button className="danger-button" disabled={pending} type="button" onClick={() => remove(item.id)}>Удалить</button></div>)}</div>
  </section>;
}
