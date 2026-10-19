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
