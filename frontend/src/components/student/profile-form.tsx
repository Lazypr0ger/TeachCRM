"use client";

import { type FormEvent, useState } from "react";
import { useRouter } from "next/navigation";
import { authenticatedJson } from "@/lib/auth-api";
import type { StudentProfile } from "@/lib/profile";

export function StudentProfileForm({ profile }: { profile: StudentProfile }) {
  const router = useRouter();
  const [pending, setPending] = useState(false);
  const [error, setError] = useState("");
  const [saved, setSaved] = useState(false);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    setPending(true);
    setError("");
    setSaved(false);
    try {
      await authenticatedJson<StudentProfile>("/api/v1/student/profile", "PATCH", {
        last_name: data.get("last_name"),
        first_name: data.get("first_name"),
        patronymic: data.get("patronymic") || null,
        grade: data.get("grade") ? Number(data.get("grade")) : null,
      });
      setSaved(true);
      router.refresh();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Не удалось сохранить профиль");
    } finally { setPending(false); }
  }

  return <form className="lesson-form management-card" onSubmit={submit}>
    <label>Фамилия<input name="last_name" required maxLength={100} defaultValue={profile.last_name} /></label>
    <label>Имя<input name="first_name" required maxLength={100} defaultValue={profile.first_name} /></label>
    <label>Отчество<input name="patronymic" maxLength={100} defaultValue={profile.patronymic ?? ""} /></label>
    <label>Класс<input name="grade" type="number" min={1} max={11} defaultValue={profile.grade ?? ""} /></label>
    {error ? <p className="form-error wide-field" role="alert">{error}</p> : null}
    {saved ? <p className="form-success wide-field" role="status">Профиль сохранён.</p> : null}
    <button className="primary-button wide-field" disabled={pending} type="submit">{pending ? "Сохраняем…" : "Сохранить"}</button>
  </form>;
}
