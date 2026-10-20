import Link from "next/link";
import { LogoutButton } from "@/components/auth/logout-button";
import { NotificationList } from "@/components/notifications/notification-list";
import { InviteStudentForm } from "@/components/teacher/invite-student-form";
import { TeacherLessonCard } from "@/components/teacher/teacher-lesson-card";
import type { Lesson } from "@/lib/lessons";
import type { NotificationPage } from "@/lib/notifications";
import { requireRole, serverGet } from "@/lib/server-auth";
import { type PublicSite, type TrialPage, trialStatus } from "@/lib/trials";

export default async function TeacherPage() {
  const user = await requireRole("TEACHER");
  const site = await serverGet<PublicSite>("/api/v1/public/site");
  const [dashboard, notifications, trials] = await Promise.all([
    serverGet<{ today_lessons: Lesson[] }>("/api/v1/teacher/dashboard"),
    serverGet<NotificationPage>("/api/v1/notifications?page_size=3"),
    site.trials_enabled ? serverGet<TrialPage>("/api/v1/teacher/trial-requests?page_size=3") : Promise.resolve(null),
  ]);
  return <main className="dashboard-shell">
    <section className="auth-card"><p>TEACHER</p><h1>Кабинет преподавателя</h1><p>Вход выполнен как {user.login}.</p><div className="dashboard-links"><Link className="primary-link" href="/teacher/schedule">Расписание</Link><Link className="secondary-button" href="/teacher/students">Ученики</Link><Link className="secondary-button" href="/teacher/finances">Финансы</Link><Link className="secondary-button" href="/teacher/notifications">Уведомления</Link>{site.trials_enabled ? <Link className="secondary-button" href="/teacher/trials">Пробные</Link> : null}</div><LogoutButton /></section>
    <InviteStudentForm />
    <section className="dashboard-wide"><h2>Уроки сегодня</h2><div className="lesson-list">{dashboard.today_lessons.length ? dashboard.today_lessons.map((lesson) => <TeacherLessonCard lesson={lesson} key={lesson.id} />) : <div className="management-card"><p>На сегодня уроков нет.</p></div>}</div></section>
    <section className="dashboard-wide"><div className="section-heading"><h2>Последние уведомления</h2><Link className="text-link" href="/teacher/notifications">Открыть все</Link></div><NotificationList items={notifications.items} userRole="TEACHER" /></section>
    <section className="dashboard-wide"><div className="section-heading"><h2>Пробные заявки</h2>{site.trials_enabled ? <Link className="text-link" href="/teacher/trials">Открыть все</Link> : null}</div>{site.trials_enabled && trials ? <div className="trial-list">{trials.items.length ? trials.items.map((trial) => <article className="management-card" key={trial.id}><p className="eyebrow">{trial.grade} класс</p><h3>{trial.name}</h3><p>{trialStatus[trial.status]}</p></article>) : <div className="management-card"><p>Новых заявок нет.</p></div>}</div> : <div className="management-card muted-section"><p>Приём пробных заявок выключен настройкой `TRIAL_BOOKING_ENABLED`.</p></div>}</section>
  </main>;
}
