"use client";

import { type FormEvent, useState } from "react";
import { useRouter } from "next/navigation";
import { postAuthenticated } from "@/lib/auth-api";
import type { Invoice, PaymentClaim } from "@/lib/billing";
import { fromMoscowInput } from "@/lib/lessons";

export function PaymentClaimForm({ invoice }: { invoice: Invoice }) {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState("");

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!window.confirm("Сообщить преподавателю о переводе? Это не проводит оплату автоматически.")) return;
    const data = new FormData(event.currentTarget);
    setPending(true);
    setError("");
    try {
      await postAuthenticated<PaymentClaim>(`/api/v1/student/invoices/${invoice.id}/payment-claims`, {
        declared_amount: data.get("declared_amount"),
        paid_at: data.get("paid_at") ? fromMoscowInput(data.get("paid_at")) : null,
        comment: data.get("comment") || null,
      });
      setOpen(false);
      router.refresh();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Не удалось отправить заявление");
    } finally { setPending(false); }
  }

  if (invoice.pending_claim_id) return <button className="secondary-button" type="button" disabled>Ожидает подтверждения</button>;
  if (!invoice.can_submit_claim) return null;
  return open ? <form className="stack-form claim-form" onSubmit={submit}>
    <label>Сумма перевода, ₽<input name="declared_amount" type="number" min="0.01" max={invoice.outstanding} step="0.01" defaultValue={invoice.outstanding} required /></label>
    <label>Когда перевели, по Москве<input name="paid_at" type="datetime-local" /></label>
    <label>Комментарий<textarea name="comment" rows={2} maxLength={1000} /></label>
    {error ? <p className="form-error" role="alert">{error}</p> : null}
    <div className="card-actions"><button className="primary-button" disabled={pending} type="submit">Отправить</button><button className="secondary-button" disabled={pending} type="button" onClick={() => setOpen(false)}>Отмена</button></div>
  </form> : <button className="primary-button" type="button" onClick={() => setOpen(true)}>Я оплатил</button>;
}
