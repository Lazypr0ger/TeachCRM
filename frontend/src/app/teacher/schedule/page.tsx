import Link from "next/link";
import { LessonCreateForm } from "@/components/teacher/lesson-create-form";
import { TeacherLessonCard } from "@/components/teacher/teacher-lesson-card";
import { AvailabilityManager } from "@/components/teacher/availability-manager";
import type { LessonList } from "@/lib/lessons";
import type { AvailabilityException, AvailabilityRule } from "@/lib/scheduling";
import { requireRole, serverGet } from "@/lib/server-auth";
import type { StudentList } from "@/lib/students";

type SearchParams = Promise<{ student_id?: string; lesson_status?: string; page?: string }>;

export default async function SchedulePage({ searchParams }: { searchParams: SearchParams }) {
  await requireRole("TEACHER");
  const filters = await searchParams;
  const students = await serverGet<StudentList>("/api/v1/teacher/students?page_size=100&sort=name");
  const query = new URLSearchParams();
  if (filters.student_id) query.set("student_id", filters.student_id);
  if (filters.lesson_status) query.set("lesson_status", filters.lesson_status);
  if (filters.page) query.set("page", filters.page);
  const [lessons, rules, exceptions] = await Promise.all([
    serverGet<LessonList>(`/api/v1/teacher/lessons?${query}`),
    serverGet<AvailabilityRule[]>("/api/v1/teacher/availability-rules"),
    serverGet<AvailabilityException[]>("/api/v1/teacher/availability-exceptions"),
  ]);
  const pageHref = (page: number) => {
    const target = new URLSearchParams(query);
    target.set("page", String(page));
    return `/teacher/schedule?${target}`;
  };

  return <main className="management-shell">
    <header className="management-header"><div><Link className="text-link" href="/teacher">← В кабинет</Link><h1>Расписание</h1><p>Индивидуальные уроки, время указано по Москве.</p></div></header>
    <LessonCreateForm students={students.items.filter((student) => student.status !== "SUSPENDED")} />
    <AvailabilityManager rules={rules} exceptions={exceptions} />
    <section className="management-card schedule-filters"><form className="filters-form compact-filters">
      <label>Ученик<select name="student_id" defaultValue={filters.student_id ?? ""}><option value="">Все</option>{students.items.map((student) => <option value={student.id} key={student.id}>{student.last_name} {student.first_name}</option>)}</select></label>
      <label>Статус<select name="lesson_status" defaultValue={filters.lesson_status ?? ""}><option value="">Все</option><option value="SCHEDULED">Запланированные</option><option value="COMPLETED">Проведённые</option><option value="CANCELLED">Отменённые</option></select></label>
      <button className="primary-button" type="submit">Показать</button>
    </form></section>
    <section className="lesson-list" aria-label="Уроки">{lessons.items.length ? lessons.items.map((lesson) => <TeacherLessonCard lesson={lesson} key={lesson.id} />) : <div className="management-card"><p>Уроки не найдены.</p></div>}</section>
    {lessons.total > lessons.page_size ? <nav className="pagination" aria-label="Страницы списка">{lessons.page > 1 ? <Link className="secondary-button" href={pageHref(lessons.page - 1)}>Назад</Link> : <span />}<span>Страница {lessons.page}</span>{lessons.page * lessons.page_size < lessons.total ? <Link className="secondary-button" href={pageHref(lessons.page + 1)}>Далее</Link> : <span />}</nav> : null}
  </main>;
}
