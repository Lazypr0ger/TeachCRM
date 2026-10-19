import Link from "next/link";
import { InvoiceAdjustmentForm } from "@/components/teacher/invoice-adjustment-form";
import { MonthlyInvoiceForm } from "@/components/teacher/monthly-invoice-form";
import { PaymentClaimActions } from "@/components/teacher/payment-claim-actions";
import { PaymentReverseForm } from "@/components/teacher/payment-reverse-form";
import { type BillingSummary, type Invoice, type Payment, type PaymentClaim, rubles } from "@/lib/billing";
import { formatMoscow } from "@/lib/lessons";
import { requireRole, serverGet } from "@/lib/server-auth";
import type { StudentList } from "@/lib/students";

export default async function TeacherFinancesPage() {
  await requireRole("TEACHER");
  const [summary, invoices, claims, payments, students] = await Promise.all([
    serverGet<BillingSummary>("/api/v1/teacher/finances/summary"),
    serverGet<{ items: Invoice[]; total: number }>("/api/v1/teacher/invoices"),
    serverGet<PaymentClaim[]>("/api/v1/teacher/payment-claims?claim_status=PENDING"),
    serverGet<Payment[]>("/api/v1/teacher/payments"),
    serverGet<StudentList>("/api/v1/teacher/students?page_size=100"),
  ]);
  const reversedIds = new Set(payments.map((payment) => payment.reversal_of_payment_id).filter((id): id is string => id !== null));
  return <main className="management-shell">
    <header className="management-header"><div><Link className="text-link" href="/teacher">← В кабинет</Link><h1>Финансы</h1><p>Ручной учёт начислений и подтверждённых переводов. CRM не принимает деньги.</p></div></header>
    <section className="summary-grid"><article className="management-card"><p className="eyebrow">Начислено</p><h2>{rubles(summary.accrued_total)}</h2></article><article className="management-card"><p className="eyebrow">Подтверждено</p><h2>{rubles(summary.received_total)}</h2></article><article className="management-card"><p className="eyebrow">Ожидается</p><h2>{rubles(summary.outstanding_total)}</h2></article></section>
    <section className="management-card"><h2>Помесячное начисление</h2><MonthlyInvoiceForm students={students.items} /></section>
    <section className="dashboard-section"><h2>Ожидают решения</h2><div className="lesson-list">{claims.length ? claims.map((claim) => <article className="management-card" key={claim.id}><p className="eyebrow">{claim.student_name}</p><h3>{rubles(claim.declared_amount)}</h3>{claim.comment ? <p>{claim.comment}</p> : null}<PaymentClaimActions claim={claim} /></article>) : <div className="management-card"><p>Новых заявлений нет.</p></div>}</div></section>
    <section className="dashboard-section"><h2>Начисления</h2><div className="lesson-list">{invoices.items.map((invoice) => <article className="management-card" key={invoice.id}><div className="lesson-card-heading"><div><p className="eyebrow">Срок {formatMoscow(invoice.due_at)}</p><h3>{rubles(invoice.total)}</h3></div><span className={`status invoice-${invoice.status.toLowerCase()}`}>{rubles(invoice.outstanding)} осталось</span></div>{invoice.items.map((item) => <p key={item.id}>{item.description} — {rubles(item.subtotal)}</p>)}<InvoiceAdjustmentForm invoiceId={invoice.id} /></article>)}</div></section>
    <section className="dashboard-section"><h2>Подтверждённые операции</h2><div className="lesson-list">{payments.length ? payments.map((payment) => <article className="management-card" key={payment.id}><p className="eyebrow">{formatMoscow(payment.received_at)}</p><h3>{rubles(payment.amount)}</h3>{payment.reversal_of_payment_id ? <p>Обратная операция: {payment.reversal_reason}</p> : reversedIds.has(payment.id) ? <p className="helper-text">Исправлен обратной операцией</p> : <PaymentReverseForm paymentId={payment.id} />}</article>) : <div className="management-card"><p>Подтверждённых операций пока нет.</p></div>}</div></section>
  </main>;
}
