import Link from "next/link";
import { SiteSettingsForm } from "@/components/teacher/site-settings-form";
import { requireRole, serverGet } from "@/lib/server-auth";
import type { TeacherSiteSettings } from "@/lib/trials";

export default async function TeacherSettingsPage() {
  await requireRole("TEACHER");
  const settings = await serverGet<TeacherSiteSettings>("/api/v1/teacher/settings/site");
  return <main className="management-shell narrow-management">
    <header className="management-header"><div><Link className="text-link" href="/teacher">← В кабинет</Link><h1>Публичный сайт</h1><p>Контент главной страницы и доступность формы пробного занятия.</p></div></header>
    <section className="management-card"><SiteSettingsForm initial={settings} /></section>
  </main>;
}
