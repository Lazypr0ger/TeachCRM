import Link from "next/link";
import { StudentProfileForm } from "@/components/student/profile-form";
import type { StudentProfile } from "@/lib/profile";
import { requireRole, serverGet } from "@/lib/server-auth";

export default async function StudentProfilePage() {
  await requireRole("STUDENT");
  const profile = await serverGet<StudentProfile>("/api/v1/student/profile");
  return <main className="management-shell narrow-management"><header className="management-header"><div><Link className="text-link" href="/student">← На главную</Link><h1>Мой профиль</h1><p>В CRM хранятся только ФИО и класс.</p></div></header><StudentProfileForm profile={profile} /></main>;
}
