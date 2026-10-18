"use client";

import { useRouter } from "next/navigation";
import { type FormEvent, useState } from "react";
import { postAuthenticated } from "@/lib/auth-api";
import { fromMoscowInput, type Lesson } from "@/lib/lessons";
import type { Student } from "@/lib/students";

export function LessonCreateForm({ students }: { students: Student[] }) {
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
      await postAuthenticated<Lesson>("/api/v1/teacher/lessons", {
        student_id: data.get("student_id"),
        title: data.get("title"),
        description: data.get("description") || null,
        starts_at: fromMoscowInput(data.get("starts_at")),
        ends_at: fromMoscowInput(data.get("ends_at")),
        join_url: data.get("join_url") || null,
      });
      form.reset();
      setMessage("Урок добавлен в расписание");
      router.refresh();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Не удалось создать урок");
    } finally {
      setPending(false);
    }
  }

  return <section className="management-card">
    <h2>Добавить урок</h2>
    {students.length ? <form className="lesson-form" onSubmit={submit}>
      <label>Ученик<select name="student_id" required>{students.map((student) => <option value={student.id} key={student.id}>{student.last_name} {student.first_name}</option>)}</select></label>
      <label>Тема<input name="title" required maxLength={200} /></label>
      <label>Начало по Москве<input name="starts_at" type="datetime-local" required /></label>
      <label>Окончание по Москве<input name="ends_at" type="datetime-local" required /></label>
      <label className="wide-field">Описание<textarea name="description" maxLength={10000} rows={3} /></label>
      <label className="wide-field">Ссылка подключения HTTPS<input name="join_url" type="url" pattern="https://.*" /></label>
      {error ? <p className="form-error wide-field" role="alert">{error}</p> : null}
      {message ? <p className="form-success wide-field" role="status">{message}</p> : null}
      <button className="primary-button" disabled={pending} type="submit">{pending ? "Сохраняем…" : "Создать урок"}</button>
    </form> : <p>Сначала создайте хотя бы одного доступного ученика.</p>}
  </section>;
}
