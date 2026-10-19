import Link from "next/link";
import { PaymentClaimForm } from "@/components/student/payment-claim-form";
import { type BillingSummary, type Invoice, type PaymentClaim, rubles } from "@/lib/billing";
import { formatMoscow } from "@/lib/lessons";
import { requireRole, serverGet } from "@/lib/server-auth";

const statuses: Record<Invoice["status"], string> = {
  UNPAID: "К оплате",
  PARTIALLY_PAID: "Оплачено частично",
  PAID: "Оплачено",
  OVERDUE: "Просрочено",
};

export default async function StudentBillingPage() {
  await requireRole("STUDENT");
  const [summary, invoices, claims] = await Promise.all([
    serverGet<BillingSummary>("/api/v1/student/billing"),
    serverGet<{ items: Invoice[]; total: number }>("/api/v1/student/invoices"),
    serverGet<PaymentClaim[]>("/api/v1/student/payment-claims"),
  ]);
  return <main className="management-shell narrow-management">
    <header className="management-header"><div><Link className="text-link" href="/student">← На главную</Link><h1>Финансы</h1><p>CRM показывает ручной учёт начислений и подтверждений. Оплата выполняется вне системы.</p></div></header>
    {summary.profile ? <section className="management-card"><p className="eyebrow">Текущий тариф</p><h2>{rubles(summary.profile.effective_price_per_lesson)} за урок</h2><p>{summary.profile.billing_mode === "PER_LESSON" ? "Оплата проведённых занятий" : "Предоплата за календарный месяц"} · скидка {summary.profile.effective_discount_percent}%</p></section> : <section className="management-card muted-section"><h2>Тариф ещё не настроен</h2><p>До настройки преподавателем начисления не создаются.</p></section>}
    <section className="summary-grid"><article className="management-card"><p className="eyebrow">Начислено</p><h2>{rubles(summary.accrued_total)}</h2></article><article className="management-card"><p className="eyebrow">Подтверждено</p><h2>{rubles(summary.received_total)}</h2></article><article className="management-card"><p className="eyebrow">Остаток</p><h2>{rubles(summary.outstanding_total)}</h2></article></section>
    <section className="dashboard-section"><h2>Начисления</h2><div className="lesson-list">{invoices.items.length ? invoices.items.map((invoice) => { const lastClaim = claims.find((claim) => claim.invoice_id === invoice.id); return <article className="management-card" key={invoice.id}><div className="lesson-card-heading"><div><p className="eyebrow">Срок {formatMoscow(invoice.due_at)}</p><h3>{rubles(invoice.total)}</h3></div><span className={`status invoice-${invoice.status.toLowerCase()}`}>{statuses[invoice.status]}</span></div>{invoice.items.map((item) => <p key={item.id}>{item.description} — {rubles(item.subtotal)}</p>)}{Number(invoice.discount_amount) > 0 ? <p className="helper-text">Скидка {invoice.discount_percent}%: −{rubles(invoice.discount_amount)}</p> : null}<p><strong>Остаток: {rubles(invoice.outstanding)}</strong></p>{lastClaim?.status === "REJECTED" ? <p className="form-error">Предыдущее заявление отклонено{lastClaim.rejection_reason ? `: ${lastClaim.rejection_reason}` : "."}</p> : null}<PaymentClaimForm invoice={invoice} /></article>; }) : <div className="management-card"><p>Начислений пока нет.</p></div>}</div></section>
  </main>;
}
