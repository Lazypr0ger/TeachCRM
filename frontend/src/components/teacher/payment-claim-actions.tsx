"use client";

import { type FormEvent, useState } from "react";
import { useRouter } from "next/navigation";
import { postAuthenticated } from "@/lib/auth-api";
import type { Payment, PaymentClaim } from "@/lib/billing";
import { fromMoscowInput, toMoscowInput } from "@/lib/lessons";

export function PaymentClaimActions({ claim }: { claim: PaymentClaim }) {
  const router = useRouter();
  const [pending, setPending] = useState(false);
  const [error, setError] = useState("");
  const [requestId] = useState(() => crypto.randomUUID());

  async function confirm(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    setPending(true);
    setError("");
    try {
      await postAuthenticated<Payment>(`/api/v1/teacher/payment-claims/${claim.id}/confirm`, {
        confirmed_amount: data.get("confirmed_amount"),
        received_at: fromMoscowInput(data.get("received_at")),
        idempotency_key: requestId,
      });
      router.refresh();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Не удалось подтвердить заявление");
    } finally { setPending(false); }
  }

  async function reject() {
    const reason = window.prompt("Причина отклонения (необязательно)") ?? undefined;
    if (reason === undefined) return;
    setPending(true);
    setError("");
    try {
      await postAuthenticated<PaymentClaim>(`/api/v1/teacher/payment-claims/${claim.id}/reject`, { reason: reason || null });
      router.refresh();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Не удалось отклонить заявление");
    } finally { setPending(false); }
  }

  return <div className="claim-actions"><form className="compact-action-form" onSubmit={confirm}><label>Подтвердить сумму, ₽<input name="confirmed_amount" type="number" min="0.01" step="0.01" defaultValue={claim.declared_amount} required /></label><label>Дата получения по Москве<input name="received_at" type="datetime-local" defaultValue={toMoscowInput(new Date().toISOString())} required /></label><button className="primary-button" disabled={pending} type="submit">Подтвердить</button></form><button className="danger-button" disabled={pending} type="button" onClick={reject}>Отклонить</button>{error ? <p className="form-error" role="alert">{error}</p> : null}</div>;
}
