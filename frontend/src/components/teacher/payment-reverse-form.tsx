"use client";

import { type FormEvent, useState } from "react";
import { useRouter } from "next/navigation";
import { postAuthenticated } from "@/lib/auth-api";
import type { Payment } from "@/lib/billing";
import { fromMoscowInput, toMoscowInput } from "@/lib/lessons";

export function PaymentReverseForm({ paymentId }: { paymentId: string }) {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState("");
  const [requestId] = useState(() => crypto.randomUUID());
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!window.confirm("Создать обратную операцию и снова открыть задолженность?")) return;
    const data = new FormData(event.currentTarget);
    setPending(true);
    setError("");
    try {
      await postAuthenticated<Payment>(`/api/v1/teacher/payments/${paymentId}/reverse`, {
        reason: data.get("reason"),
        reversed_at: fromMoscowInput(data.get("reversed_at")),
        idempotency_key: requestId,
      });
      router.refresh();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Не удалось создать обратную операцию");
    } finally { setPending(false); }
  }
  return open ? <form className="compact-action-form" onSubmit={submit}><label>Причина<input name="reason" minLength={3} maxLength={1000} required /></label><label>Дата исправления<input name="reversed_at" type="datetime-local" defaultValue={toMoscowInput(new Date().toISOString())} required /></label><button className="danger-button" disabled={pending} type="submit">Исправить</button><button className="secondary-button" type="button" onClick={() => setOpen(false)}>Отмена</button>{error ? <p className="form-error" role="alert">{error}</p> : null}</form> : <button className="danger-button" type="button" onClick={() => setOpen(true)}>Обратная операция</button>;
}
