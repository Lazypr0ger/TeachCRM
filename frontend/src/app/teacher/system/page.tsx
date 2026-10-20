import Link from "next/link";
import { formatMoscow } from "@/lib/lessons";
import { requireRole, serverGet } from "@/lib/server-auth";

type Diagnostics = {
  status: "ok" | "attention";
  pending_outbox: number;
  retrying_outbox: number;
  due_outbox: number;
  oldest_pending_at: string | null;
  active_sessions: number;
};

export default async function SystemPage() {
  await requireRole("TEACHER");
  const data = await serverGet<Diagnostics>("/api/v1/teacher/system/diagnostics");
  return <main className="management-shell narrow-management">
    <header className="management-header"><div><Link className="text-link" href="/teacher">← В кабинет</Link><h1>Состояние системы</h1><p>Очередь внутренних уведомлений и активные сессии.</p></div><span className={`status ${data.status === "ok" ? "status-active" : "status-invited"}`}>{data.status === "ok" ? "Работает штатно" : "Требует внимания"}</span></header>
    <section className="summary-grid"><article className="management-card"><p className="eyebrow">Очередь</p><h2>{data.pending_outbox}</h2><p>ожидают доставки</p></article><article className="management-card"><p className="eyebrow">Повторные попытки</p><h2>{data.retrying_outbox}</h2><p>событий</p></article><article className="management-card"><p className="eyebrow">Сессии</p><h2>{data.active_sessions}</h2><p>активных</p></article></section>
    {data.due_outbox ? <section className="management-card muted-section"><h2>Задержка доставки</h2><p>Сейчас готовы к обработке: {data.due_outbox}. Самое старое событие: {data.oldest_pending_at ? formatMoscow(data.oldest_pending_at) : "время неизвестно"}.</p><p className="warning-text">Проверьте, что worker запущен и имеет доступ к PostgreSQL.</p></section> : null}
  </main>;
}
