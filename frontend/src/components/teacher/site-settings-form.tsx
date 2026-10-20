"use client";

import { type FormEvent, useState } from "react";
import { authenticatedJson } from "@/lib/auth-api";
import type { TeacherSiteSettings } from "@/lib/trials";

const lines = (value: string) => value.split("\n").map((item) => item.trim()).filter(Boolean);

export function SiteSettingsForm({ initial }: { initial: TeacherSiteSettings }) {
  const [settings, setSettings] = useState(initial);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState("");
  const [saved, setSaved] = useState(false);

  async function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    setPending(true);
    setError("");
    setSaved(false);
    try {
      const updated = await authenticatedJson<TeacherSiteSettings>("/api/v1/teacher/settings/site", "PATCH", {
        brand_name: data.get("brand_name"),
        tagline: data.get("tagline"),
        about_text: data.get("about_text"),
        directions: lines(String(data.get("directions") ?? "")),
        advantages: lines(String(data.get("advantages") ?? "")),
        confirmed_results: lines(String(data.get("confirmed_results") ?? "")),
        pricing_text: data.get("pricing_text"),
        privacy_text: data.get("privacy_text"),
        trials_enabled: data.get("trials_enabled") === "on",
        version: settings.version,
      });
      setSettings(updated);
      setSaved(true);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Не удалось сохранить настройки");
    } finally {
      setPending(false);
    }
  }

  return <form className="lesson-form site-settings-form" key={settings.version} onSubmit={save}>
    <label>Название<input name="brand_name" required maxLength={120} defaultValue={settings.brand_name} /></label>
    <label>Заголовок<input name="tagline" maxLength={300} defaultValue={settings.tagline ?? ""} /></label>
    <label className="wide-field">Описание<textarea name="about_text" rows={5} maxLength={5000} defaultValue={settings.about_text ?? ""} /></label>
    <label>Направления, по одному в строке<textarea name="directions" rows={6} defaultValue={settings.directions.join("\n")} /></label>
    <label>Преимущества, по одному в строке<textarea name="advantages" rows={6} defaultValue={settings.advantages.join("\n")} /></label>
    <label className="wide-field">Подтверждённые результаты<textarea name="confirmed_results" rows={4} defaultValue={settings.confirmed_results.join("\n")} /></label>
    <label className="wide-field">Описание стоимости<textarea name="pricing_text" rows={4} maxLength={3000} defaultValue={settings.pricing_text ?? ""} /></label>
    <label className="wide-field">Политика конфиденциальности<textarea name="privacy_text" rows={5} maxLength={10000} defaultValue={settings.privacy_text ?? ""} /></label>
    <label className="checkbox-label wide-field"><input name="trials_enabled" type="checkbox" defaultChecked={settings.configured_trials_enabled} /> Принимать заявки на пробное занятие</label>
    {!settings.trial_feature_available ? <p className="warning-text wide-field">Общий флаг `TRIAL_BOOKING_ENABLED` выключен. Настройка сохранится, но публичная форма останется закрытой.</p> : null}
    {error ? <p className="form-error wide-field" role="alert">{error}</p> : null}
    {saved ? <p className="form-success wide-field" role="status">Настройки сохранены.</p> : null}
    <button className="primary-button wide-field" disabled={pending} type="submit">{pending ? "Сохранение…" : "Сохранить и опубликовать"}</button>
  </form>;
}
