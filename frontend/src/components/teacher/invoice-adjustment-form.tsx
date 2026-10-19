"use client";

import { type FormEvent, useState } from "react";
import { useRouter } from "next/navigation";
import { postAuthenticated } from "@/lib/auth-api";
import type { Invoice } from "@/lib/billing";

export function InvoiceAdjustmentForm({ invoiceId }: { invoiceId: string }) {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState("");
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    setPending(true);
    setError("");
    try {
      await postAuthenticated<Invoice>(`/api/v1/teacher/invoices/${invoiceId}/adjustments`, { amount: data.get("amount"), reason: data.get("reason") });
      setOpen(false);
      router.refresh();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Не удалось добавить корректировку");
    } finally { setPending(false); }
  }
  return open ? <form className="compact-action-form" onSubmit={submit}><label>Сумма, ₽<input name="amount" type="number" step="0.01" required /></label><label>Причина<input name="reason" minLength={3} maxLength={500} required /></label><button className="secondary-button" disabled={pending} type="submit">Применить</button><button className="secondary-button" type="button" onClick={() => setOpen(false)}>Отмена</button>{error ? <p className="form-error" role="alert">{error}</p> : null}</form> : <button className="secondary-button" type="button" onClick={() => setOpen(true)}>Корректировка</button>;
}
