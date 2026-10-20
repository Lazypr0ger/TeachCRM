import Link from "next/link";
import { WeekCalendar } from "@/components/calendar/week-calendar";
import { LessonCreateForm } from "@/components/teacher/lesson-create-form";
import { TeacherLessonCard } from "@/components/teacher/teacher-lesson-card";
import { AvailabilityManager } from "@/components/teacher/availability-manager";
import { RecurrenceManager } from "@/components/teacher/recurrence-manager";
import { TeacherRescheduleManager } from "@/components/teacher/reschedule-manager";
import type { LessonList } from "@/lib/lessons";
import { weekRange } from "@/lib/calendar";
import type { AvailabilityException, AvailabilityRule, RecurrenceRule, RescheduleRequest } from "@/lib/scheduling";
import { requireRole, serverGet } from "@/lib/server-auth";
import type { StudentList } from "@/lib/students";

type SearchParams = Promise<{ student_id?: string; lesson_status?: string; page?: string; week?: string }>;

export default async function SchedulePage({ searchParams }: { searchParams: SearchParams }) {
  await requireRole("TEACHER");
  const filters = await searchParams;
  const week = weekRange(filters.week);
  const students = await serverGet<StudentList>("/api/v1/teacher/students?page_size=100&sort=name");
  const query = new URLSearchParams();
  if (filters.student_id) query.set("student_id", filters.student_id);
  if (filters.lesson_status) query.set("lesson_status", filters.lesson_status);
  if (filters.page) query.set("page", filters.page);
  const calendarQuery = new URLSearchParams({ date_from: `${week.start}T00:00:00+03:00`, date_to: `${week.end}T00:00:00+03:00`, page_size: "100" });
  const [lessons, calendarLessons, rules, exceptions, recurrenceRules, rescheduleRequests] = await Promise.all([
    serverGet<LessonList>(`/api/v1/teacher/lessons?${query}`),
    serverGet<LessonList>(`/api/v1/teacher/lessons?${calendarQuery}`),
    serverGet<AvailabilityRule[]>("/api/v1/teacher/availability-rules"),
    serverGet<AvailabilityException[]>("/api/v1/teacher/availability-exceptions"),
    serverGet<RecurrenceRule[]>("/api/v1/teacher/recurrence-rules"),
    serverGet<RescheduleRequest[]>("/api/v1/teacher/reschedule-requests"),
  ]);
  const pageHref = (page: number) => {
    const target = new URLSearchParams(query);
    target.set("page", String(page));
    return `/teacher/schedule?${target}`;
  };

  return <main className="management-shell">
    <header className="management-header"><div><Link className="text-link" href="/teacher">← В кабинет</Link><h1>Расписание</h1><p>Индивидуальные уроки, время указано по Москве.</p></div></header>
    <LessonCreateForm students={students.items.filter((student) => student.status !== "SUSPENDED")} />
    <WeekCalendar lessons={calendarLessons.items} markers={exceptions.map((item) => ({ id: item.id, starts_at: item.starts_at, ends_at: item.ends_at, label: item.kind === "BLOCKED" ? "Время заблокировано" : "Дополнительное доступное время", tone: item.kind === "BLOCKED" ? "busy" as const : "available" as const }))} week={week.start} basePath="/teacher/schedule" showStudent />
    <AvailabilityManager rules={rules} exceptions={exceptions} />
    <RecurrenceManager rules={recurrenceRules} students={students.items.filter((student) => student.status !== "SUSPENDED")} />
    <TeacherRescheduleManager requests={rescheduleRequests} />
    <section className="management-card schedule-filters"><form className="filters-form compact-filters">
      <label>Ученик<select name="student_id" defaultValue={filters.student_id ?? ""}><option value="">Все</option>{students.items.map((student) => <option value={student.id} key={student.id}>{student.last_name} {student.first_name}</option>)}</select></label>
      <label>Статус<select name="lesson_status" defaultValue={filters.lesson_status ?? ""}><option value="">Все</option><option value="SCHEDULED">Запланированные</option><option value="COMPLETED">Проведённые</option><option value="CANCELLED">Отменённые</option></select></label>
      <button className="primary-button" type="submit">Показать</button>
    </form></section>
    <section className="lesson-list" aria-label="Уроки">{lessons.items.length ? lessons.items.map((lesson) => <TeacherLessonCard lesson={lesson} key={lesson.id} />) : <div className="management-card"><p>Уроки не найдены.</p></div>}</section>
    {lessons.total > lessons.page_size ? <nav className="pagination" aria-label="Страницы списка">{lessons.page > 1 ? <Link className="secondary-button" href={pageHref(lessons.page - 1)}>Назад</Link> : <span />}<span>Страница {lessons.page}</span>{lessons.page * lessons.page_size < lessons.total ? <Link className="secondary-button" href={pageHref(lessons.page + 1)}>Далее</Link> : <span />}</nav> : null}
  </main>;
}
