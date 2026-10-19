"use client";

import { type FormEvent, useEffect, useState } from "react";
import { authenticatedJson } from "@/lib/auth-api";
import { type BillingProfile, rubles } from "@/lib/billing";

export function BillingProfileForm({ studentId }: { studentId: string }) {
  const [profile, setProfile] = useState<BillingProfile | null>(null);
  const [mode, setMode] = useState<"PER_LESSON" | "MONTHLY">("PER_LESSON");
  const [loaded, setLoaded] = useState(false);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    fetch(`/api/v1/teacher/students/${studentId}/billing-profile`, { cache: "no-store" })
      .then(async (response) => {
        if (response.status === 404) return null;
        if (!response.ok) throw new Error("Не удалось загрузить финансовый профиль");
        return response.json() as Promise<BillingProfile>;
      })
      .then((value) => {
        setProfile(value);
        if (value) setMode(value.billing_mode);
        setLoaded(true);
      })
      .catch((caught) => { setError(caught instanceof Error ? caught.message : "Ошибка загрузки"); setLoaded(true); });
  }, [studentId]);

  async function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    setPending(true);
    setError("");
    try {
      const updated = await authenticatedJson<BillingProfile>(`/api/v1/teacher/students/${studentId}/billing-profile`, "PATCH", {
        billing_mode: mode,
        price_per_lesson: data.get("price_per_lesson"),
        family_discount_enabled: data.get("family_discount_enabled") === "on",
        monthly_due_day: mode === "MONTHLY" ? Number(data.get("monthly_due_day")) : null,
        version: profile?.version ?? null,
      });
      setProfile(updated);
      setMode(updated.billing_mode);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Не удалось сохранить тариф");
    } finally { setPending(false); }
  }

  return <section className="management-card">
    <div className="section-heading"><div><p className="eyebrow">Финансовый учёт</p><h2>Тариф и скидка</h2></div>{profile ? <span className="status status-active">Скидка {profile.effective_discount_percent}%</span> : null}</div>
    {!loaded ? <p className="helper-text">Загрузка…</p> : <form className="lesson-form" key={profile?.version ?? "new"} onSubmit={save}>
      <label>Режим<select name="billing_mode" value={mode} onChange={(event) => setMode(event.target.value as "PER_LESSON" | "MONTHLY")}><option value="PER_LESSON">За каждый проведённый урок</option><option value="MONTHLY">Предоплата за календарный месяц</option></select></label>
      <label>Цена урока, ₽<input name="price_per_lesson" type="number" min="0" max="9999999999.99" step="0.01" required defaultValue={profile?.price_per_lesson ?? "0.00"} /></label>
      {mode === "MONTHLY" ? <label>День оплаты<input name="monthly_due_day" type="number" min="1" max="31" required defaultValue={profile?.monthly_due_day ?? 1} /></label> : null}
      <label className="checkbox-label"><input name="family_discount_enabled" type="checkbox" defaultChecked={profile?.family_discount_enabled ?? false} /> Семейная скидка 20%</label>
      {profile ? <p className="helper-text wide-field">Итоговая цена урока: <strong>{rubles(profile.effective_price_per_lesson)}</strong>. Скидки не складываются, применяется максимальная.</p> : <p className="helper-text wide-field">Начисления появятся только после сохранения тарифа.</p>}
      {mode === "MONTHLY" ? <p className="helper-text wide-field">Действующее правило: предоплата запланированных занятий календарного месяца. Если выбранного дня нет, используется последний день месяца.</p> : null}
      {error ? <p className="form-error wide-field" role="alert">{error}</p> : null}
      <button className="primary-button wide-field" disabled={pending} type="submit">{pending ? "Сохранение…" : "Сохранить тариф"}</button>
    </form>}
  </section>;
}
