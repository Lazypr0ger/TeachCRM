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
