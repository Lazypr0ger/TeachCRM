"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { postAuthenticated } from "@/lib/auth-api";
import {
  type NotificationItem,
  notificationTarget,
} from "@/lib/notifications";
import { formatMoscow } from "@/lib/lessons";

export function NotificationList({
  items,
  userRole,
}: {
  items: NotificationItem[];
  userRole: "STUDENT" | "TEACHER";
}) {
  const router = useRouter();
  const [pending, setPending] = useState(false);
  const [error, setError] = useState("");

  async function markRead(item: NotificationItem) {
    setPending(true);
    setError("");
    try {
      if (!item.read_at) {
        await postAuthenticated(`/api/v1/notifications/${item.id}/read`);
      }
      const target = notificationTarget(item, userRole);
      if (target) router.push(target);
      else router.refresh();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Не удалось прочитать уведомление");
    } finally {
      setPending(false);
    }
  }

  async function markAllRead() {
    setPending(true);
    setError("");
    try {
      await postAuthenticated("/api/v1/notifications/read-all");
      router.refresh();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Не удалось обновить уведомления");
    } finally {
      setPending(false);
    }
  }

  return <>
    {items.some((item) => !item.read_at) ? <button className="secondary-button" disabled={pending} type="button" onClick={markAllRead}>Прочитать все</button> : null}
    {error ? <p className="form-error" role="alert">{error}</p> : null}
    <section className="notification-list" aria-label="Уведомления">
      {items.length ? items.map((item) => <article className={`management-card notification-card ${item.read_at ? "" : "notification-unread"}`} key={item.id}>
        <div><p className="eyebrow">{formatMoscow(item.created_at)}</p><h2>{item.title}</h2><p>{item.body}</p></div>
        <button className="secondary-button" disabled={pending} type="button" onClick={() => markRead(item)}>{notificationTarget(item, userRole) ? "Открыть" : item.read_at ? "Прочитано" : "Прочитать"}</button>
      </article>) : <div className="management-card"><p>Уведомлений пока нет.</p></div>}
    </section>
  </>;
}
