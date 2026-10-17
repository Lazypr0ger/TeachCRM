import { LogoutButton } from "@/components/auth/logout-button";
import { InviteStudentForm } from "@/components/teacher/invite-student-form";
import { requireRole } from "@/lib/server-auth";

export default async function TeacherPage() {
  const user = await requireRole("TEACHER");
  return <main className="dashboard-shell">
    <section className="auth-card"><p>TEACHER</p><h1>Кабинет преподавателя</h1><p>Вход выполнен как {user.login}.</p><LogoutButton /></section>
    <InviteStudentForm />
  </main>;
}
