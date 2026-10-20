import type { Lesson } from "./lessons";

export type CalendarMarker = {
  id: string;
  starts_at: string;
  ends_at: string;
  label: string;
  tone: "busy" | "available";
};

const dateFormatter = new Intl.DateTimeFormat("en-CA", {
  timeZone: "Europe/Moscow",
  year: "numeric",
  month: "2-digit",
  day: "2-digit",
});

export function moscowDateKey(value: string | Date): string {
  return dateFormatter.format(typeof value === "string" ? new Date(value) : value);
}

function plainDate(value: string): Date {
  return new Date(`${value}T00:00:00Z`);
}

export function shiftDate(value: string, days: number): string {
  const date = plainDate(value);
  date.setUTCDate(date.getUTCDate() + days);
  return date.toISOString().slice(0, 10);
}

export function mondayFor(value?: string): string {
  const key = value && /^\d{4}-\d{2}-\d{2}$/.test(value) ? value : moscowDateKey(new Date());
  const date = plainDate(key);
  const offset = (date.getUTCDay() + 6) % 7;
  return shiftDate(key, -offset);
}

export function weekRange(value?: string): { start: string; end: string; days: string[] } {
  const start = mondayFor(value);
  return { start, end: shiftDate(start, 7), days: Array.from({ length: 7 }, (_, i) => shiftDate(start, i)) };
}

export function groupLessons(lessons: Lesson[]): Map<string, Lesson[]> {
  const grouped = new Map<string, Lesson[]>();
  for (const lesson of lessons) {
    const key = moscowDateKey(lesson.starts_at);
    grouped.set(key, [...(grouped.get(key) ?? []), lesson]);
  }
  return grouped;
}
