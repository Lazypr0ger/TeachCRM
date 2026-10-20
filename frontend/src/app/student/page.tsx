import Link from "next/link";
import { StudentLessonCard } from "@/components/student/lesson-card";
import { rubles, type BillingSummary } from "@/lib/billing";
import { formatMoscow, type Lesson } from "@/lib/lessons";
import type { NotificationPage } from "@/lib/notifications";
import { requireRole, serverGet } from "@/lib/server-auth";

export default async function StudentPage() {
  const user = await requireRole("STUDENT");
  const [dashboard, billing, notifications] = await Promise.all([
    serverGet<{ next_lesson: Lesson | null }>("/api/v1/student/dashboard"),
    serverGet<BillingSummary>("/api/v1/student/billing"),
    serverGet<NotificationPage>("/api/v1/notifications?page_size=1"),
  ]);
  const latest = notifications.items[0];
  return <main className="management-shell narrow-management"><section className="management-card"><p>STUDENT</p><h1>Кабинет ученика</h1><p>Вход выполнен как {user.login}.</p></section><section className="dashboard-section"><h2>Ближайший урок</h2>{dashboard.next_lesson ? <StudentLessonCard lesson={dashboard.next_lesson} compact /> : <div className="management-card"><p>Запланированных уроков пока нет.</p></div>}</section><section className="dashboard-section summary-grid"><article className="management-card"><p className="eyebrow">Задолженность</p><h2>{rubles(billing.outstanding_total)}</h2><Link className="text-link" href="/student/billing">Открыть финансы</Link></article><article className="management-card"><p className="eyebrow">Последнее уведомление</p>{latest ? <><h2>{latest.title}</h2><p>{formatMoscow(latest.created_at)}</p><Link className="text-link" href="/student/notifications">Открыть</Link></> : <p>Уведомлений пока нет.</p>}</article></section><section className="management-card muted-section"><h2>Прогресс</h2><p>В разработке</p></section></main>;
}
