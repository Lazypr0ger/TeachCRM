import Link from "next/link";
import { NotificationList } from "@/components/notifications/notification-list";
import {
  lessonDuration,
  moscowTime,
  studentInitials,
  type TeacherDashboard,
} from "@/lib/dashboard";
import { lessonStatus } from "@/lib/lessons";
import type { NotificationPage } from "@/lib/notifications";
import { requireRole, serverGet } from "@/lib/server-auth";

const dateFormatter = new Intl.DateTimeFormat("ru-RU", {
  timeZone: "Europe/Moscow",
  weekday: "long",
  day: "numeric",
  month: "long",
});

export default async function TeacherPage() {
  await requireRole("TEACHER");
  const [dashboard, notifications] = await Promise.all([
    serverGet<TeacherDashboard>("/api/v1/teacher/dashboard"),
    serverGet<NotificationPage>("/api/v1/notifications?page_size=3"),
  ]);
  const nextLesson = dashboard.next_lesson;
  const stats = [
    { label: "Занятий сегодня", value: dashboard.lessons_today, hint: "Открыть расписание", href: "/teacher/schedule", tone: "blue", glyph: "К" },
    { label: "Заявок об оплате", value: dashboard.pending_payment_claims, hint: "Ожидают решения", href: "/teacher/finances", tone: "green", glyph: "₽" },
    { label: "Ответов на ДЗ сегодня", value: dashboard.homework_submissions_today, hint: "Приняты сервером", href: "/teacher/schedule", tone: "amber", glyph: "ДЗ" },
    { label: "Запросов переноса", value: dashboard.pending_reschedule_requests, hint: "Ожидают ответа", href: "/teacher/schedule", tone: "red", glyph: "↔" },
  ];

  return <main className="teacher-dashboard">
    <header className="dashboard-heading"><div><p className="eyebrow">Обзор</p><h1>Добрый день!</h1><p>{dateFormatter.format(new Date())} · Москва</p></div></header>

    <section className="dashboard-stat-grid" aria-label="Сводка">{stats.map((stat) => <Link className={`dashboard-stat stat-${stat.tone}`} href={stat.href} key={stat.label}>
      <span className="dashboard-stat-icon" aria-hidden="true">{stat.glyph}</span>
      <span><small>{stat.label}</small><strong>{stat.value}</strong><small>{stat.hint}</small></span>
      <span aria-hidden="true">→</span>
    </Link>)}</section>

    <div className="dashboard-work-grid">
      <section className="dashboard-panel dashboard-schedule">
        <div className="section-heading"><h2>Сегодняшнее расписание</h2><Link className="text-link" href="/teacher/schedule">Открыть расписание →</Link></div>
        {dashboard.today_lessons.length ? <ol className="dashboard-timeline">{dashboard.today_lessons.map((lesson) => <li key={lesson.id}>
          <div className="dashboard-lesson-time"><strong>{moscowTime(lesson.starts_at)}–{moscowTime(lesson.ends_at)}</strong><small>{lessonDuration(lesson.starts_at, lesson.ends_at)}</small></div>
          <span className="student-avatar" aria-hidden="true">{studentInitials(lesson.student_name)}</span>
          <div className="dashboard-lesson-person"><strong>{lesson.student_name}</strong><small>{lesson.title}</small></div>
          <span className={`status status-${lesson.status.toLowerCase()}`}>{lessonStatus[lesson.status]}</span>
          {lesson.join_url && lesson.status === "SCHEDULED" ? <a className="secondary-button compact-button" href={lesson.join_url} target="_blank" rel="noreferrer">Открыть урок</a> : null}
        </li>)}</ol> : <div className="dashboard-empty"><strong>Сегодня занятий нет</strong><p>Можно использовать день для подготовки материалов.</p></div>}
      </section>

      <aside className="dashboard-panel next-lesson-panel">
        <div className="section-heading"><h2>Ближайшее занятие</h2></div>
        {nextLesson ? <div className="next-lesson-content">
          <p className="next-lesson-time">{moscowTime(nextLesson.starts_at)}–{moscowTime(nextLesson.ends_at)}</p>
          <div className="next-student"><span className="student-avatar" aria-hidden="true">{studentInitials(nextLesson.student_name)}</span><span><strong>{nextLesson.student_name}</strong><small>{nextLesson.title}</small></span></div>
          <p>{new Intl.DateTimeFormat("ru-RU", { timeZone: "Europe/Moscow", dateStyle: "long" }).format(new Date(nextLesson.starts_at))} · {lessonDuration(nextLesson.starts_at, nextLesson.ends_at)}</p>
          {nextLesson.join_url ? <a className="primary-link" href={nextLesson.join_url} target="_blank" rel="noreferrer">Открыть урок →</a> : <Link className="secondary-button" href="/teacher/schedule">Открыть расписание</Link>}
        </div> : <div className="dashboard-empty"><strong>Занятий пока нет</strong><p>Следующее запланированное занятие появится здесь.</p><Link className="text-link" href="/teacher/schedule">Открыть расписание</Link></div>}
      </aside>
    </div>

    <section className="dashboard-panel dashboard-notifications">
      <div className="section-heading"><h2>Последние уведомления</h2><Link className="text-link" href="/teacher/notifications">Все уведомления →</Link></div>
      <NotificationList items={notifications.items} userRole="TEACHER" />
    </section>
  </main>;
}
