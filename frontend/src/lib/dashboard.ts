import type { Lesson } from "./lessons";

export type TeacherDashboard = {
  today_lessons: Lesson[];
  next_lesson: Lesson | null;
  lessons_today: number;
  pending_payment_claims: number;
  homework_submissions_today: number;
  pending_reschedule_requests: number;
};

export function moscowTime(value: string): string {
  return new Intl.DateTimeFormat("ru-RU", {
    timeZone: "Europe/Moscow",
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(value));
}

export function lessonDuration(startsAt: string, endsAt: string): string {
  const minutes = Math.round((new Date(endsAt).getTime() - new Date(startsAt).getTime()) / 60_000);
  const hours = Math.floor(minutes / 60);
  const rest = minutes % 60;
  if (!hours) return `${rest} мин`;
  return rest ? `${hours} ч ${rest} мин` : `${hours} ч`;
}

export function studentInitials(name: string): string {
  return name.split(/\s+/).filter(Boolean).slice(0, 2).map((part) => part[0]).join("").toUpperCase();
}
