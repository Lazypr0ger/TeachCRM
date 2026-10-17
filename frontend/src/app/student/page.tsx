import { LogoutButton } from "@/components/auth/logout-button";
import { requireRole } from "@/lib/server-auth";

export default async function StudentPage() {
  const user = await requireRole("STUDENT");
  return <main className="auth-shell"><section className="auth-card"><p>STUDENT</p><h1>Кабинет ученика</h1><p>Вход выполнен как {user.login}. Расписание и занятия появятся на следующих этапах.</p><LogoutButton /></section></main>;
}
