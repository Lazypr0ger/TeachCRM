import Link from "next/link";
import { BillingProfileForm } from "@/components/teacher/billing-profile-form";
import { StudentEditDrawer } from "@/components/teacher/student-edit-drawer";
import { type BillingSummary, type Invoice, rubles } from "@/lib/billing";
import { type StudentHomeworkSummary, homeworkState } from "@/lib/homework";
import { formatMoscow, type LessonList, lessonStatus } from "@/lib/lessons";
import { requireRole, serverGet } from "@/lib/server-auth";
import { type Student, studentStatus } from "@/lib/students";

const tabs = [
  ["overview", "Обзор"],
  ["lessons", "Занятия"],
  ["homework", "Домашние задания"],
  ["program", "Программа"],
  ["finance", "Финансы"],
] as const;
type Tab = (typeof tabs)[number][0];

export default async function StudentPage({
  params,
  searchParams,
}: {
  params: Promise<{ id: string }>;
  searchParams: Promise<{ tab?: string }>;
}) {
  await requireRole("TEACHER");
  const { id } = await params;
  const requestedTab = (await searchParams).tab;
  const tab: Tab = tabs.some(([value]) => value === requestedTab) ? requestedTab as Tab : "overview";
  const [student, lessons, homeworks, billing, invoices] = await Promise.all([
    serverGet<Student>(`/api/v1/teacher/students/${id}`),
    serverGet<LessonList>(`/api/v1/teacher/lessons?student_id=${id}&page_size=100`),
    serverGet<StudentHomeworkSummary[]>(`/api/v1/teacher/students/${id}/homework`),
    serverGet<BillingSummary>(`/api/v1/teacher/finances/summary?student_id=${id}`),
    serverGet<{ items: Invoice[]; total: number }>(`/api/v1/teacher/invoices?student_id=${id}`),
  ]);
  const fullName = [student.last_name, student.first_name, student.patronymic].filter(Boolean).join(" ");
  const initials = `${student.last_name[0] ?? ""}${student.first_name[0] ?? ""}`.toUpperCase();
  const now = Date.now();
  const nextLesson = lessons.items
    .filter((lesson) => lesson.status === "SCHEDULED" && new Date(lesson.ends_at).getTime() > now)
    .sort((a, b) => a.starts_at.localeCompare(b.starts_at))[0];
  const completed = lessons.items.filter((lesson) => lesson.status === "COMPLETED").length;
  const acceptedHomework = homeworks.filter((item) => item.state === "ACCEPTED").length;

  return <main className="management-shell student-profile-page">
    <Link className="text-link" href="/teacher/students">← Все ученики</Link>
    <header className="student-profile-hero">
      <span className="profile-avatar" aria-hidden="true">{initials}</span>
      <div><p className="eyebrow">Профиль ученика</p><h1>{fullName}</h1><p>{student.grade ? `${student.grade} класс` : "Класс не указан"} · {student.login}</p></div>
      <span className={`status status-${student.status.toLowerCase()}`}>{studentStatus[student.status]}</span>
      <StudentEditDrawer student={student} />
    </header>

    <nav className="profile-tabs" aria-label="Разделы профиля">{tabs.map(([value, label]) => <Link aria-current={tab === value ? "page" : undefined} className={tab === value ? "active" : ""} href={`/teacher/students/${id}?tab=${value}`} key={value}>{label}</Link>)}</nav>

    {tab === "overview" ? <>
      <section className="profile-stat-grid" aria-label="Сводка ученика">
        <article className="mini-stat"><small>Проведено занятий</small><strong>{completed}</strong></article>
        <article className="mini-stat"><small>Ответов на ДЗ</small><strong>{acceptedHomework}</strong></article>
        <article className="mini-stat"><small>Задолженность</small><strong>{rubles(billing.outstanding_total)}</strong></article>
      </section>
      <div className="profile-overview-grid">
        <section className="management-card"><h2>Основные данные</h2><dl className="profile-details"><div><dt>ФИО</dt><dd>{fullName}</dd></div><div><dt>Класс</dt><dd>{student.grade ?? "Не указан"}</dd></div><div><dt>Логин</dt><dd>{student.login}</dd></div><div><dt>Последний вход</dt><dd>{student.last_login_at ? formatMoscow(student.last_login_at) : "Ещё не входил"}</dd></div></dl></section>
        <section className="management-card"><div className="section-heading"><h2>Следующее занятие</h2><Link className="text-link" href={`/teacher/students/${id}?tab=lessons`}>Все занятия</Link></div>{nextLesson ? <div className="profile-next-lesson"><p className="eyebrow">{formatMoscow(nextLesson.starts_at)}</p><h3>{nextLesson.title}</h3>{nextLesson.description ? <p>{nextLesson.description}</p> : null}{nextLesson.join_url ? <a className="primary-link" href={nextLesson.join_url} target="_blank" rel="noreferrer">Открыть урок</a> : null}</div> : <div className="dashboard-empty"><strong>Не запланировано</strong><p>Будущих занятий пока нет.</p></div>}</section>
      </div>
    </> : null}

    {tab === "lessons" ? <section className="management-card profile-list-section"><div className="section-heading"><h2>Занятия</h2><span>{lessons.total}</span></div>{lessons.items.length ? <div className="profile-record-list">{lessons.items.map((lesson) => <article key={lesson.id}><div><strong>{lesson.title}</strong><small>{formatMoscow(lesson.starts_at)}</small></div><span className={`status status-${lesson.status.toLowerCase()}`}>{lessonStatus[lesson.status]}</span></article>)}</div> : <div className="dashboard-empty"><strong>Занятий нет</strong></div>}</section> : null}

    {tab === "homework" ? <section className="management-card profile-list-section"><div className="section-heading"><h2>Домашние задания</h2><span>{homeworks.length}</span></div>{homeworks.length ? <div className="profile-record-list">{homeworks.map((item) => <article key={item.lesson_id}><div><strong>{item.lesson_title}</strong><small>{formatMoscow(item.lesson_starts_at)}</small>{item.assignment_description ? <p>{item.assignment_description}</p> : null}{item.submitted_at ? <small>Ответ отправлен {formatMoscow(item.submitted_at)}</small> : item.due_at ? <small>Срок {formatMoscow(item.due_at)}</small> : null}</div><span className={`status homework-${item.state.toLowerCase()}`}>{homeworkState[item.state]}</span></article>)}</div> : <div className="dashboard-empty"><strong>Домашних заданий нет</strong></div>}</section> : null}

    {tab === "program" ? <section className="management-card honest-placeholder"><p className="eyebrow">Индивидуальная программа</p><h2>В разработке</h2><p>В v1 нет модели учебной программы и прогресса по темам. Здесь не отображаются вымышленные проценты или результаты.</p></section> : null}

    {tab === "finance" ? <><section className="profile-stat-grid"><article className="mini-stat"><small>Начислено</small><strong>{rubles(billing.accrued_total)}</strong></article><article className="mini-stat"><small>Подтверждено</small><strong>{rubles(billing.received_total)}</strong></article><article className="mini-stat"><small>Остаток</small><strong>{rubles(billing.outstanding_total)}</strong></article></section><BillingProfileForm studentId={student.id} /><section className="management-card profile-list-section"><h2>Начисления</h2>{invoices.items.length ? <div className="profile-record-list">{invoices.items.map((invoice) => <article key={invoice.id}><div><strong>{rubles(invoice.total)}</strong><small>Срок {formatMoscow(invoice.due_at)}</small></div><span className={`status invoice-${invoice.status.toLowerCase()}`}>{rubles(invoice.outstanding)} осталось</span></article>)}</div> : <div className="dashboard-empty"><strong>Начислений нет</strong></div>}</section></> : null}
  </main>;
}
