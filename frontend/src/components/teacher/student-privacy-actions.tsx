"use client";

import { type FormEvent, useState } from "react";
import { useRouter } from "next/navigation";
import { postAuthenticated } from "@/lib/auth-api";

export function StudentPrivacyActions({ studentId, login }: { studentId: string; login: string }) {
  const router = useRouter();
  const [pending, setPending] = useState(false);
  const [error, setError] = useState("");

  async function anonymize(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    setPending(true);
    setError("");
    try {
      await postAuthenticated(`/api/v1/teacher/students/${studentId}/anonymize`, {
        confirmation: data.get("confirmation"),
      });
      router.replace("/teacher/students");
      router.refresh();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Не удалось анонимизировать данные");
      setPending(false);
    }
  }

  return <section className="management-card privacy-actions">
    <h2>Экспорт и удаление персональных данных</h2>
    <p className="helper-text">Экспорт содержит данные этого ученика в JSON. Анонимизация необратимо отзывает доступ, удаляет ФИО, класс, учебные ответы и личные файлы. Обезличенный финансовый журнал сохраняется.</p>
    <a className="secondary-button" href={`/api/v1/teacher/students/${studentId}/export`}>Скачать экспорт</a>
    <form className="stack-form" onSubmit={anonymize}><label>Для подтверждения введите логин <strong>{login}</strong><input name="confirmation" required autoComplete="off" /></label>{error ? <p className="form-error" role="alert">{error}</p> : null}<button className="danger-button" disabled={pending} type="submit">{pending ? "Анонимизация…" : "Анонимизировать ученика"}</button></form>
  </section>;
}
