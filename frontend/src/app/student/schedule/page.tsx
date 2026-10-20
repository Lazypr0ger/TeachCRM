import Link from "next/link";
import { WeekCalendar } from "@/components/calendar/week-calendar";
import { StudentAvailabilityManager } from "@/components/student/availability-manager";
import { StudentLessonCard } from "@/components/student/lesson-card";
import { StudentRescheduleManager } from "@/components/student/reschedule-manager";
import type { RescheduleRequest, StudentSchedule } from "@/lib/scheduling";
import { weekRange } from "@/lib/calendar";
import type { LessonList } from "@/lib/lessons";
import { requireRole, serverGet } from "@/lib/server-auth";

type SearchParams = Promise<{ week?: string }>;

export default async function StudentSchedulePage({ searchParams }: { searchParams: SearchParams }) {
  await requireRole("STUDENT");
  const filters = await searchParams;
  const week = weekRange(filters.week);
  const calendarQuery = new URLSearchParams({ date_from: `${week.start}T00:00:00+03:00`, date_to: `${week.end}T00:00:00+03:00`, page_size: "100" });
  const [schedule, requests, calendarLessons] = await Promise.all([
    serverGet<StudentSchedule>("/api/v1/student/schedule"),
    serverGet<RescheduleRequest[]>("/api/v1/student/reschedule-requests"),
    serverGet<LessonList>(`/api/v1/student/lessons?${calendarQuery}`),
  ]);
  return <main className="management-shell narrow-management">
    <header className="management-header"><div><Link className="text-link" href="/student">← На главную</Link><h1>Моё расписание</h1><p>Уроки и отметки времени по Москве.</p></div></header>
    <WeekCalendar lessons={calendarLessons.items} markers={schedule.availability.map((item) => ({ id: item.id, starts_at: item.starts_at, ends_at: item.ends_at, label: item.state === "BUSY" ? "Я занят" : "Я свободен", tone: item.state === "BUSY" ? "busy" as const : "available" as const }))} week={week.start} basePath="/student/schedule" showStudent={false} />
    <StudentAvailabilityManager items={schedule.availability} />
    <StudentRescheduleManager lessons={schedule.lessons} requests={requests} />
    <section className="dashboard-section"><h2>Уроки</h2><div className="lesson-list">{schedule.lessons.length ? schedule.lessons.map((lesson) => <StudentLessonCard lesson={lesson} key={lesson.id} />) : <div className="management-card"><p>Занятий пока нет.</p></div>}</div></section>
  </main>;
}
