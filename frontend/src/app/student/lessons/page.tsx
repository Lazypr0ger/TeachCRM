import Link from "next/link";
import { StudentLessonCard } from "@/components/student/lesson-card";
import type { LessonList } from "@/lib/lessons";
import { requireRole, serverGet } from "@/lib/server-auth";

type SearchParams = Promise<{ lesson_status?: string; page?: string }>;

export default async function StudentLessonsPage({ searchParams }: { searchParams: SearchParams }) {
  await requireRole("STUDENT");
  const filters = await searchParams;
  const query = new URLSearchParams();
  if (filters.lesson_status) query.set("lesson_status", filters.lesson_status);
  if (filters.page) query.set("page", filters.page);
  const lessons = await serverGet<LessonList>(`/api/v1/student/lessons?${query}`);
  const pageHref = (page: number) => {
    const target = new URLSearchParams(query);
    target.set("page", String(page));
    return `/student/lessons?${target}`;
  };
  return <main className="management-shell narrow-management">
    <header className="management-header"><div><Link className="text-link" href="/student">← На главную</Link><h1>Мои занятия</h1></div></header>
    <section className="management-card"><form className="filters-form compact-filters"><label>Статус<select name="lesson_status" defaultValue={filters.lesson_status ?? ""}><option value="">Все</option><option value="SCHEDULED">Предстоящие</option><option value="COMPLETED">Проведённые</option><option value="CANCELLED">Отменённые</option></select></label><button className="primary-button" type="submit">Показать</button></form></section>
    <section className="lesson-list">{lessons.items.length ? lessons.items.map((lesson) => <StudentLessonCard lesson={lesson} key={lesson.id} />) : <div className="management-card"><p>Занятий пока нет.</p></div>}</section>
    {lessons.total > lessons.page_size ? <nav className="pagination" aria-label="Страницы списка">{lessons.page > 1 ? <Link className="secondary-button" href={pageHref(lessons.page - 1)}>Назад</Link> : <span />}<span>Страница {lessons.page}</span>{lessons.page * lessons.page_size < lessons.total ? <Link className="secondary-button" href={pageHref(lessons.page + 1)}>Далее</Link> : <span />}</nav> : null}
  </main>;
}
