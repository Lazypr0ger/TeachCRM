import Link from "next/link";
import { TrialRequestForm } from "@/components/public/trial-request-form";
import type { PublicSite } from "@/lib/trials";

export const dynamic = "force-dynamic";

const fallback: PublicSite = {
  brand_name: "Tutor CRM",
  tagline: "Учёба, расписание и расчёты в одном кабинете",
  about_text: null,
  directions: ["Индивидуальные занятия", "Подготовка к контрольным", "Разбор тем"],
  advantages: ["Прозрачное расписание", "Домашние задания в одном месте"],
  confirmed_results: [],
  pricing_text: null,
  privacy_text: null,
  trials_enabled: false,
  timezone: "Europe/Moscow",
};

async function publicSite(): Promise<PublicSite> {
  const apiUrl = process.env.API_INTERNAL_URL ?? "http://127.0.0.1:8000";
  try {
    const response = await fetch(`${apiUrl}/api/v1/public/site`, { cache: "no-store" });
    if (response.ok) return response.json() as Promise<PublicSite>;
  } catch {
    // The public shell stays available while the local API starts.
  }
  return fallback;
}

export default async function Home() {
  const site = await publicSite();
  return <main className="public-shell">
    <nav className="public-nav"><strong>{site.brand_name}</strong><div><a href="#directions">Направления</a>{site.trials_enabled ? <a href="#trial">Пробное занятие</a> : null}<Link className="secondary-button" href="/login">Войти</Link></div></nav>
    <section className="public-hero"><p className="eyebrow">Обучение в часовом поясе Москвы</p><h1>{site.tagline ?? site.brand_name}</h1>{site.about_text ? <p>{site.about_text}</p> : <p>Расписание, материалы и домашние задания доступны ученику в защищённом кабинете.</p>}<div className="card-actions"><Link className="primary-link" href="/login">Войти в кабинет</Link>{site.trials_enabled ? <a className="secondary-button" href="#trial">Записаться на пробное</a> : null}</div></section>
    <section className="public-capabilities" id="directions" aria-label="Направления занятий">{site.directions.map((title) => <article className="management-card" key={title}><h2>{title}</h2></article>)}</section>
    {site.advantages.length ? <section className="public-content"><h2>Как проходят занятия</h2><ul>{site.advantages.map((item) => <li key={item}>{item}</li>)}</ul></section> : null}
    {site.confirmed_results.length ? <section className="public-content"><h2>Подтверждённые результаты</h2><ul>{site.confirmed_results.map((item) => <li key={item}>{item}</li>)}</ul></section> : null}
    {site.pricing_text ? <section className="management-card public-content"><h2>Стоимость</h2><p>{site.pricing_text}</p></section> : null}
    {site.trials_enabled ? <TrialRequestForm /> : <section className="management-card public-disabled"><h2>Пробные заявки сейчас закрыты</h2><p>Активная форма появится здесь, когда преподаватель включит приём.</p></section>}
    {site.privacy_text ? <footer className="public-footer"><h2>Конфиденциальность</h2><p>{site.privacy_text}</p></footer> : null}
  </main>;
}
