import Link from "next/link";
import { InviteStudentForm } from "@/components/teacher/invite-student-form";
import { requireRole, serverGet } from "@/lib/server-auth";
import { type StudentList, studentStatus } from "@/lib/students";

type SearchParams = Promise<{
  search?: string;
  grade?: string;
  student_status?: string;
  sort?: string;
  page?: string;
}>;

export default async function StudentsPage({ searchParams }: { searchParams: SearchParams }) {
  await requireRole("TEACHER");
  const filters = await searchParams;
  const query = new URLSearchParams();
  for (const key of ["search", "grade", "student_status", "sort", "page"] as const) {
    if (filters[key]) query.set(key, filters[key]);
  }
  const students = await serverGet<StudentList>(`/api/v1/teacher/students?${query}`);
  const pageHref = (page: number) => {
    const target = new URLSearchParams(query);
    target.set("page", String(page));
    return `/teacher/students?${target}`;
  };

  return <main className="management-shell">
    <header className="management-header">
      <div><Link className="text-link" href="/teacher">← В кабинет</Link><h1>Ученики</h1><p>Всего: {students.total}</p></div>
    </header>
    <section className="management-card">
      <form className="filters-form">
        <label>Поиск<input name="search" defaultValue={filters.search} placeholder="ФИО или логин" /></label>
        <label>Класс<input name="grade" type="number" min={1} max={11} defaultValue={filters.grade} /></label>
        <label>Статус<select name="student_status" defaultValue={filters.student_status ?? ""}>
          <option value="">Все</option><option value="INVITED">Ожидает активации</option><option value="ACTIVE">Активен</option><option value="SUSPENDED">Заблокирован</option>
        </select></label>
        <label>Сортировка<select name="sort" defaultValue={filters.sort ?? "name"}>
          <option value="name">По фамилии</option><option value="created_desc">Сначала новые</option><option value="created_asc">Сначала старые</option>
        </select></label>
        <button className="primary-button" type="submit">Найти</button>
      </form>
    </section>
    <section className="student-list" aria-label="Список учеников">
      {students.items.length ? students.items.map((student) => <Link className="student-row" href={`/teacher/students/${student.id}`} key={student.id}>
        <span><strong>{student.last_name} {student.first_name} {student.patronymic}</strong><small>{student.login}</small></span>
        <span>{student.grade ? `${student.grade} класс` : "Класс не указан"}</span>
        <span className={`status status-${student.status.toLowerCase()}`}>{studentStatus[student.status]}</span>
      </Link>) : <div className="management-card"><p>Ученики не найдены.</p></div>}
    </section>
    {students.total > students.page_size ? <nav className="pagination" aria-label="Страницы списка">
      {students.page > 1 ? <Link className="secondary-button" href={pageHref(students.page - 1)}>Назад</Link> : <span />}
      <span>Страница {students.page}</span>
      {students.page * students.page_size < students.total ? <Link className="secondary-button" href={pageHref(students.page + 1)}>Далее</Link> : <span />}
    </nav> : null}
    <InviteStudentForm />
  </main>;
}
