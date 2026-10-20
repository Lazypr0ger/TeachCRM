import Link from "next/link";
import { NotificationList } from "@/components/notifications/notification-list";
import type { NotificationPage } from "@/lib/notifications";

type Filters = { type?: string; is_read?: string; date_from?: string; date_to?: string; page?: string };

export function NotificationsPage({
  data,
  filters,
  userRole,
}: {
  data: NotificationPage;
  filters: Filters;
  userRole: "STUDENT" | "TEACHER";
}) {
  const base = userRole === "STUDENT" ? "/student" : "/teacher";
  const query = new URLSearchParams();
  for (const key of ["type", "is_read", "date_from", "date_to", "page"] as const) {
    if (filters[key]) query.set(key, filters[key]);
  }
  const pageHref = (page: number) => {
    const target = new URLSearchParams(query);
    target.set("page", String(page));
    return `${base}/notifications?${target}`;
  };
  return <main className="management-shell narrow-management">
    <header className="management-header"><div><Link className="text-link" href={base}>← В кабинет</Link><h1>Уведомления</h1><p>Всего: {data.total}</p></div></header>
    <section className="management-card"><form className="filters-form notification-filters">
      <label>Тип<select name="type" defaultValue={filters.type ?? ""}><option value="">Все</option><option value="LESSON_CREATED">Новый урок</option><option value="LESSON_RESCHEDULED">Перенос</option><option value="LESSON_CANCELLED">Отмена</option><option value="HOMEWORK_ASSIGNED">Домашнее задание</option><option value="HOMEWORK_SUBMITTED">Ответ по ДЗ</option><option value="PAYMENT_CLAIM_CREATED">Заявление об оплате</option><option value="PAYMENT_CONFIRMED">Оплата подтверждена</option><option value="PAYMENT_REJECTED">Оплата отклонена</option><option value="TRIAL_RECEIVED">Пробная заявка</option><option value="SYSTEM">Системные</option></select></label>
      <label>Статус<select name="is_read" defaultValue={filters.is_read ?? ""}><option value="">Все</option><option value="false">Непрочитанные</option><option value="true">Прочитанные</option></select></label>
      <label>С даты<input name="date_from" type="date" defaultValue={filters.date_from} /></label>
      <label>До даты<input name="date_to" type="date" defaultValue={filters.date_to} /></label>
      <button className="primary-button" type="submit">Показать</button>
    </form></section>
    <NotificationList items={data.items} userRole={userRole} />
    {data.total > data.page_size ? <nav className="pagination" aria-label="Страницы списка">{data.page > 1 ? <Link className="secondary-button" href={pageHref(data.page - 1)}>Назад</Link> : <span />}<span>Страница {data.page}</span>{data.page * data.page_size < data.total ? <Link className="secondary-button" href={pageHref(data.page + 1)}>Далее</Link> : <span />}</nav> : null}
  </main>;
}
