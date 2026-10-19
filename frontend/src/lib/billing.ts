export type BillingProfile = {
  id: string;
  student_id: string;
  billing_mode: "PER_LESSON" | "MONTHLY";
  price_per_lesson: string;
  currency: "RUB";
  family_discount_enabled: boolean;
  monthly_due_day: number | null;
  monthly_settlement_rule: "PREPAY_SCHEDULED";
  effective_discount_percent: string;
  effective_price_per_lesson: string;
  version: number;
  created_at: string;
  updated_at: string;
};

export function rubles(value: string): string {
  return new Intl.NumberFormat("ru-RU", { style: "currency", currency: "RUB" }).format(Number(value));
}

export type InvoiceItem = {
  id: string;
  lesson_id: string | null;
  kind: "LESSON" | "ADJUSTMENT";
  description: string;
  quantity: string;
  unit_price: string;
  subtotal: string;
};

export type Invoice = {
  id: string;
  student_id: string;
  billing_mode_snapshot: "PER_LESSON" | "MONTHLY";
  period_start: string | null;
  period_end: string | null;
  issued_at: string;
  due_at: string;
  currency: "RUB";
  subtotal: string;
  discount_percent: string;
  discount_amount: string;
  total: string;
  allocated_total: string;
  outstanding: string;
  status: "UNPAID" | "PARTIALLY_PAID" | "PAID" | "OVERDUE";
  can_submit_claim: boolean;
  pending_claim_id: string | null;
  items: InvoiceItem[];
};

export type BillingSummary = {
  profile: BillingProfile | null;
  accrued_total: string;
  received_total: string;
  outstanding_total: string;
  overdue_total: string;
  discount_total: string;
};

export type PaymentClaim = {
  id: string;
  invoice_id: string;
  student_id: string;
  student_name: string;
  declared_amount: string;
  paid_at: string | null;
  comment: string | null;
  status: "PENDING" | "CONFIRMED" | "REJECTED";
  rejection_reason: string | null;
  decided_at: string | null;
  created_at: string;
};

export type Payment = {
  id: string;
  student_id: string;
  claim_id: string | null;
  amount: string;
  received_at: string;
  reversal_of_payment_id: string | null;
  reversal_reason: string | null;
  created_at: string;
};
