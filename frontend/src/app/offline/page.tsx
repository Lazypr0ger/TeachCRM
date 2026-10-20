import Link from "next/link";

export default function OfflinePage() {
  return <main className="auth-shell"><section className="auth-card"><p className="eyebrow">Нет подключения</p><h1>CRM временно недоступна</h1><p>Проверьте соединение и повторите попытку. Изменения расписания, заданий и финансов офлайн не сохраняются.</p><Link className="primary-link" href="/">Повторить</Link></section></main>;
}
