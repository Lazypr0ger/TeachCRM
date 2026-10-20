"use client";

import { type FormEvent, useState } from "react";
import { useRouter } from "next/navigation";
import { authenticatedJson, postAuthenticated } from "@/lib/auth-api";
import { fromMoscowInput, toMoscowInput } from "@/lib/lessons";
import type { TrialRequest, TrialStatus } from "@/lib/trials";

type Conversion = {
  student_id: string;
  login: string;
  created: boolean;
  activation_url: string | null;
  expires_at: string | null;
};

export function TrialActions({ trial }: { trial: TrialRequest }) {
  const router = useRouter();
  const [pending, setPending] = useState(false);
  const [error, setError] = useState("");
  const [conversion, setConversion] = useState<Conversion | null>(null);

  async function changeStatus(status: TrialStatus, starts?: string, ends?: string) {
    setPending(true);
    setError("");
    try {
      await authenticatedJson(`/api/v1/teacher/trial-requests/${trial.id}`, "PATCH", {
        status,
        confirmed_start: starts ?? null,
        confirmed_end: ends ?? null,
        version: trial.version,
      });
      router.refresh();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Не удалось изменить заявку");
    } finally { setPending(false); }
  }

  async function confirm(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    await changeStatus("CONFIRMED", fromMoscowInput(data.get("starts_at")), fromMoscowInput(data.get("ends_at")));
  }

  async function convert(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    setPending(true);
    setError("");
    try {
      const result = await postAuthenticated<Conversion>(`/api/v1/teacher/trial-requests/${trial.id}/convert`, { login: data.get("login") || null });
      setConversion(result);
      router.refresh();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Не удалось создать ученика");
    } finally { setPending(false); }
  }

  const start = trial.preferred_start ?? new Date(Date.now() + 86400000).toISOString();
  const end = trial.preferred_end ?? new Date(Date.now() + 90000000).toISOString();
  return <div className="trial-actions">
    {trial.status === "NEW" ? <button className="secondary-button" disabled={pending} type="button" onClick={() => changeStatus("IN_REVIEW")}>Взять в работу</button> : null}
    {["NEW", "IN_REVIEW", "RESCHEDULE_REQUESTED"].includes(trial.status) ? <form className="compact-action-form" onSubmit={confirm}><label>Начало по Москве<input name="starts_at" type="datetime-local" defaultValue={toMoscowInput(start)} required /></label><label>Окончание по Москве<input name="ends_at" type="datetime-local" defaultValue={toMoscowInput(end)} required /></label><button className="primary-button" disabled={pending} type="submit">Подтвердить время</button></form> : null}
    {trial.status === "CONFIRMED" ? <button className="primary-button" disabled={pending} type="button" onClick={() => changeStatus("COMPLETED")}>Отметить проведённым</button> : null}
    {["NEW", "IN_REVIEW", "RESCHEDULE_REQUESTED"].includes(trial.status) ? <button className="danger-button" disabled={pending} type="button" onClick={() => changeStatus("REJECTED")}>Отклонить</button> : null}
    {trial.status === "CONFIRMED" ? <button className="danger-button" disabled={pending} type="button" onClick={() => changeStatus("CANCELLED")}>Отменить</button> : null}
    {trial.status === "COMPLETED" && !trial.converted_student_id ? <form className="compact-action-form" onSubmit={convert}><label>Логин ученика (необязательно)<input name="login" minLength={3} maxLength={120} pattern="[a-zA-Z0-9_.-]+" /></label><button className="primary-button" disabled={pending} type="submit">Создать ученика</button></form> : null}
    {trial.converted_student_id ? <p className="form-success">Ученик создан.</p> : null}
    {conversion?.activation_url ? <div className="invitation-result" role="status"><strong>Логин: {conversion.login}</strong><a className="text-link" href={conversion.activation_url}>{conversion.activation_url}</a><span>Передайте ссылку ученику вручную.</span></div> : null}
    {error ? <p className="form-error" role="alert">{error}</p> : null}
  </div>;
}
