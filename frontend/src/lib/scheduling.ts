import type { Lesson } from "./lessons";

export type AvailabilityRule = {
  id: string;
  timezone: string;
  weekday: number;
  local_start_time: string;
  local_end_time: string;
  week_parity: "ALL" | "A" | "B";
  cycle_anchor_date: string;
  effective_from: string;
  effective_until: string | null;
  is_available: boolean;
};

export type AvailabilityException = {
  id: string;
  starts_at: string;
  ends_at: string;
  kind: "BLOCKED" | "AVAILABLE_OVERRIDE";
  private_reason: string | null;
};

export type StudentAvailability = {
  id: string;
  starts_at: string;
  ends_at: string;
  state: "AVAILABLE" | "BUSY";
  conflicts_with_lesson: boolean;
};

export type StudentSchedule = {
  lessons: Lesson[];
  availability: StudentAvailability[];
};

export const weekdays = [
  "Понедельник",
  "Вторник",
  "Среда",
  "Четверг",
  "Пятница",
  "Суббота",
  "Воскресенье",
];

export const parityLabel = { ALL: "каждую неделю", A: "неделя A", B: "неделя B" };
