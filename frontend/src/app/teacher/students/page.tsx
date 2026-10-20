import Link from "next/link";
import { InviteStudentForm } from "@/components/teacher/invite-student-form";
import { rubles } from "@/lib/billing";
import { formatMoscow } from "@/lib/lessons";
import { requireRole, serverGet } from "@/lib/server-auth";
import { type StudentList, studentStatus } from "@/lib/students";

type SearchParams = Promise<{
  search?: string;
  grade?: string;
  student_status?: string;
  has_debt?: string;
  sort?: string;
  page?: string;
}>;

function initials(firstName: string, lastName: string): string {
  return `${lastName[0] ?? ""}${firstName[0] ?? ""}`.toUpperCase();
}

export default async function StudentsPage({ searchParams }: { searchParams: SearchParams }) {
  await requireRole("TEACHER");
  const filters = await searchParams;
  const query = new URLSearchParams();
  for (const key of ["search", "grade", "student_status", "has_debt", "sort", "page"] as const) {
    if (filters[key]) query.set(key, filters[key]);
  }
  const students = await serverGet<StudentList>(`/api/v1/teacher/students?${query}`);
  const pageHref = (page: number) => {
    const target = new URLSearchParams(query);
    target.set("page", String(page));
    return `/teacher/students?${target}`;
  };
  const summary = [
    ["Всего учеников", students.status_counts.TOTAL],
    ["Активны", students.status_counts.ACTIVE],
    ["Ожидают активации", students.status_counts.INVITED],
    ["Заблокированы", students.status_counts.SUSPENDED],
  ];

  return <main className="management-shell students-page">
    <header className="management-header"><div><p className="eyebrow">Обучение</p><h1>Ученики</h1><p>Учётные записи, ближайшие занятия и финансовое состояние.</p></div><InviteStudentForm /></header>

    <section className="students-summary" aria-label="Сводка по ученикам">{summary.map(([label, value]) => <article className="mini-stat" key={label}><small>{label}</small><strong>{value}</strong></article>)}</section>

    <section className="management-card students-filters">
      <form className="filters-form">
        <label>Поиск<input name="search" defaultValue={filters.search} placeholder="ФИО или логин" /></label>
        <label>Класс<input name="grade" type="number" min={1} max={11} defaultValue={filters.grade} /></label>
        <label>Статус<select name="student_status" defaultValue={filters.student_status ?? ""}><option value="">Все</option><option value="INVITED">Ожидает активации</option><option value="ACTIVE">Активен</option><option value="SUSPENDED">Заблокирован</option></select></label>
        <label>Оплата<select name="has_debt" defaultValue={filters.has_debt ?? ""}><option value="">Любая</option><option value="true">Есть задолженность</option><option value="false">Нет задолженности</option></select></label>
        <label>Сортировка<select name="sort" defaultValue={filters.sort ?? "name"}><option value="name">По фамилии</option><option value="created_desc">Сначала новые</option><option value="created_asc">Сначала старые</option></select></label>
        <button className="primary-button" type="submit">Применить</button>
      </form>
    </section>

    <section className="student-table-wrap" aria-label="Список учеников">
      {students.items.length ? <table className="student-table">
        <thead><tr><th>Ученик</th><th>Класс</th><th>Следующее занятие</th><th>Задолженность</th><th>Статус</th><th><span className="sr-only">Действие</span></th></tr></thead>
        <tbody>{students.items.map((student) => {
          const name = [student.last_name, student.first_name, student.patronymic].filter(Boolean).join(" ");
          return <tr key={student.id}>
            <td data-label="Ученик"><div className="student-identity"><span className="student-avatar" aria-hidden="true">{initials(student.first_name, student.last_name)}</span><span><strong>{name}</strong><small>{student.login}</small></span></div></td>
            <td data-label="Класс">{student.grade ? `${student.grade} класс` : "Не указан"}</td>
            <td data-label="Следующее занятие">{student.next_lesson_at ? formatMoscow(student.next_lesson_at) : <span className="muted-value">Не запланировано</span>}</td>
            <td data-label="Задолженность" className={Number(student.outstanding_total) > 0 ? "debt-value" : ""}>{rubles(student.outstanding_total)}</td>
            <td data-label="Статус"><span className={`status status-${student.status.toLowerCase()}`}>{studentStatus[student.status]}</span></td>
            <td><Link className="secondary-button compact-button" href={`/teacher/students/${student.id}`}>Открыть</Link></td>
          </tr>;
        })}</tbody>
      </table> : <div className="management-card dashboard-empty"><strong>Ученики не найдены</strong><p>Измените фильтры или добавьте нового ученика.</p></div>}
    </section>

    {students.total > students.page_size ? <nav className="pagination" aria-label="Страницы списка">{students.page > 1 ? <Link className="secondary-button" href={pageHref(students.page - 1)}>Назад</Link> : <span />}<span>Страница {students.page}</span>{students.page * students.page_size < students.total ? <Link className="secondary-button" href={pageHref(students.page + 1)}>Далее</Link> : <span />}</nav> : null}
  </main>;
}
