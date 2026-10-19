import { NotificationsPage } from "@/components/notifications/notifications-page";
import type { NotificationPage } from "@/lib/notifications";
import { requireRole, serverGet } from "@/lib/server-auth";

type SearchParams = Promise<{ type?: string; is_read?: string; date_from?: string; date_to?: string; page?: string }>;

export default async function TeacherNotificationsPage({ searchParams }: { searchParams: SearchParams }) {
  await requireRole("TEACHER");
  const filters = await searchParams;
  const query = new URLSearchParams(filters as Record<string, string>);
  const data = await serverGet<NotificationPage>(`/api/v1/notifications?${query}`);
  return <NotificationsPage data={data} filters={filters} userRole="TEACHER" />;
}
