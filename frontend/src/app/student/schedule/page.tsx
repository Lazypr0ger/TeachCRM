import Link from "next/link";
import { StudentAvailabilityManager } from "@/components/student/availability-manager";
import { StudentLessonCard } from "@/components/student/lesson-card";
import type { StudentSchedule } from "@/lib/scheduling";
import { requireRole, serverGet } from "@/lib/server-auth";

export default async function StudentSchedulePage() {
  await requireRole("STUDENT");
  const schedule = await serverGet<StudentSchedule>("/api/v1/student/schedule");
  return <main className="management-shell narrow-management">
    <header className="management-header"><div><Link className="text-link" href="/student">← На главную</Link><h1>Моё расписание</h1><p>Уроки и отметки времени по Москве.</p></div></header>
    <StudentAvailabilityManager items={schedule.availability} />
    <section className="dashboard-section"><h2>Уроки</h2><div className="lesson-list">{schedule.lessons.length ? schedule.lessons.map((lesson) => <StudentLessonCard lesson={lesson} key={lesson.id} />) : <div className="management-card"><p>Занятий пока нет.</p></div>}</div></section>
  </main>;
}
