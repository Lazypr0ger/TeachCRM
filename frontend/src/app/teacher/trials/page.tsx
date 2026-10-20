import Link from "next/link";
import { TrialActions } from "@/components/teacher/trial-actions";
import { formatMoscow } from "@/lib/lessons";
import { requireRole, serverGet } from "@/lib/server-auth";
import { type TrialPage, trialStatus } from "@/lib/trials";

type SearchParams = Promise<{ request_status?: string; page?: string }>;

export default async function TrialsPage({ searchParams }: { searchParams: SearchParams }) {
  await requireRole("TEACHER");
  const filters = await searchParams;
  const query = new URLSearchParams();
  if (filters.request_status) query.set("request_status", filters.request_status);
  if (filters.page) query.set("page", filters.page);
  const trials = await serverGet<TrialPage>(`/api/v1/teacher/trial-requests?${query}`);
  const pageHref = (page: number) => {
    const target = new URLSearchParams(query);
    target.set("page", String(page));
    return `/teacher/trials?${target}`;
  };
  return <main className="management-shell">
    <header className="management-header"><div><Link className="text-link" href="/teacher">← В кабинет</Link><h1>Пробные занятия</h1><p>Всего заявок: {trials.total}</p></div></header>
    <section className="management-card"><form className="filters-form compact-filters"><label>Статус<select name="request_status" defaultValue={filters.request_status ?? ""}><option value="">Все</option>{Object.entries(trialStatus).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label><button className="primary-button" type="submit">Показать</button></form></section>
    <section className="trial-list">{trials.items.length ? trials.items.map((trial) => <article className="management-card" key={trial.id}><div className="lesson-card-heading"><div><p className="eyebrow">{trial.grade} класс · {formatMoscow(trial.created_at)}</p><h2>{trial.name}</h2></div><span className={`status trial-${trial.status.toLowerCase()}`}>{trialStatus[trial.status]}</span></div>{trial.goal ? <p><strong>Цель:</strong> {trial.goal}</p> : null}{trial.comment ? <p>{trial.comment}</p> : null}{trial.possible_existing_student ? <p className="warning-text">Возможно, ученик уже существует — проверьте список вручную.</p> : null}{trial.confirmed_start && trial.confirmed_end ? <p>Подтверждено: {formatMoscow(trial.confirmed_start)}–{formatMoscow(trial.confirmed_end)}</p> : trial.preferred_start && trial.preferred_end ? <p>Пожелание: {formatMoscow(trial.preferred_start)}–{formatMoscow(trial.preferred_end)}</p> : null}<TrialActions trial={trial} /></article>) : <div className="management-card"><p>Заявок пока нет.</p></div>}</section>
    {trials.total > trials.page_size ? <nav className="pagination" aria-label="Страницы списка">{trials.page > 1 ? <Link className="secondary-button" href={pageHref(trials.page - 1)}>Назад</Link> : <span />}<span>Страница {trials.page}</span>{trials.page * trials.page_size < trials.total ? <Link className="secondary-button" href={pageHref(trials.page + 1)}>Далее</Link> : <span />}</nav> : null}
  </main>;
}
