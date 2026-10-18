import Link from "next/link";
import { LogoutButton } from "@/components/auth/logout-button";
import { InviteStudentForm } from "@/components/teacher/invite-student-form";
import { TeacherLessonCard } from "@/components/teacher/teacher-lesson-card";
import type { Lesson } from "@/lib/lessons";
import { requireRole, serverGet } from "@/lib/server-auth";

export default async function TeacherPage() {
  const user = await requireRole("TEACHER");
  const dashboard = await serverGet<{ today_lessons: Lesson[] }>("/api/v1/teacher/dashboard");
  return <main className="dashboard-shell">
    <section className="auth-card"><p>TEACHER</p><h1>Кабинет преподавателя</h1><p>Вход выполнен как {user.login}.</p><div className="dashboard-links"><Link className="primary-link" href="/teacher/schedule">Расписание</Link><Link className="secondary-button" href="/teacher/students">Ученики</Link></div><LogoutButton /></section>
    <InviteStudentForm />
    <section className="dashboard-wide"><h2>Уроки сегодня</h2><div className="lesson-list">{dashboard.today_lessons.length ? dashboard.today_lessons.map((lesson) => <TeacherLessonCard lesson={lesson} key={lesson.id} />) : <div className="management-card"><p>На сегодня уроков нет.</p></div>}</div></section>
  </main>;
}
