import Link from "next/link";
import { LogoutButton } from "@/components/auth/logout-button";
import { StudentLessonCard } from "@/components/student/lesson-card";
import type { Lesson } from "@/lib/lessons";
import { requireRole, serverGet } from "@/lib/server-auth";

export default async function StudentPage() {
  const user = await requireRole("STUDENT");
  const dashboard = await serverGet<{ next_lesson: Lesson | null }>("/api/v1/student/dashboard");
  return <main className="management-shell narrow-management"><section className="management-card"><p>STUDENT</p><h1>Кабинет ученика</h1><p>Вход выполнен как {user.login}.</p><div className="dashboard-links"><Link className="primary-link" href="/student/lessons">Все занятия</Link><LogoutButton /></div></section><section className="dashboard-section"><h2>Ближайший урок</h2>{dashboard.next_lesson ? <StudentLessonCard lesson={dashboard.next_lesson} compact /> : <div className="management-card"><p>Запланированных уроков пока нет.</p></div>}</section><section className="management-card muted-section"><h2>Прогресс</h2><p>В разработке</p></section></main>;
}
