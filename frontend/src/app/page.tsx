import Link from "next/link";
import { TrialRequestForm } from "@/components/public/trial-request-form";
import type { PublicSite } from "@/lib/trials";

export const dynamic = "force-dynamic";

const capabilities = [
  ["Ученики", "Приглашения и защищённые личные кабинеты"],
  ["Расписание", "Уроки, повторения и согласование переносов"],
  ["Финансы", "Учёт начислений без обработки денег"],
];

async function publicSite(): Promise<PublicSite> {
  const apiUrl = process.env.API_INTERNAL_URL ?? "http://127.0.0.1:8000";
  try {
    const response = await fetch(`${apiUrl}/api/v1/public/site`, { cache: "no-store" });
    if (response.ok) return response.json() as Promise<PublicSite>;
  } catch {
    // The public shell stays available while the local API starts.
  }
  return { trials_enabled: false };
}

export default async function Home() {
  const site = await publicSite();
  return <main className="public-shell">
    <nav className="public-nav"><strong>Tutor CRM</strong><div><a href="#directions">Возможности</a>{site.trials_enabled ? <a href="#trial">Пробное занятие</a> : null}<Link className="secondary-button" href="/login">Войти</Link></div></nav>
    <section className="public-hero"><p className="eyebrow">Локальная версия</p><h1>Учёба, расписание и расчёты в одном кабинете</h1><p>Преподаватель планирует занятия и ведёт учёт, ученик видит только собственные уроки, задания и начисления.</p><div className="card-actions"><Link className="primary-link" href="/login">Войти в кабинет</Link>{site.trials_enabled ? <a className="secondary-button" href="#trial">Записаться на пробное</a> : null}</div></section>
    <section className="public-capabilities" id="directions" aria-label="Возможности системы">{capabilities.map(([title, description]) => <article className="management-card" key={title}><h2>{title}</h2><p>{description}</p></article>)}</section>
    {site.trials_enabled ? <TrialRequestForm /> : <section className="management-card public-disabled"><h2>Пробные заявки сейчас закрыты</h2><p>Активная форма появится здесь, когда преподаватель включит приём.</p></section>}
  </main>;
}
