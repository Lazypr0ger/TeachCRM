export type LessonStatus = "SCHEDULED" | "COMPLETED" | "CANCELLED";

export type Lesson = {
  id: string;
  teacher_id: string;
  student_id: string;
  student_name: string;
  title: string;
  description: string | null;
  starts_at: string;
  ends_at: string;
  join_url: string | null;
  status: LessonStatus;
  recurrence_rule_id: string | null;
  recurrence_instance_key: string | null;
  completed_at: string | null;
  version: number;
  created_at: string;
  updated_at: string;
};

export type LessonList = {
  items: Lesson[];
  total: number;
  page: number;
  page_size: number;
};

export const lessonStatus: Record<LessonStatus, string> = {
  SCHEDULED: "Запланирован",
  COMPLETED: "Проведён",
  CANCELLED: "Отменён",
};

export function formatMoscow(value: string): string {
  return new Intl.DateTimeFormat("ru-RU", {
    timeZone: "Europe/Moscow",
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value));
}

export function toMoscowInput(value: string): string {
  const parts = new Intl.DateTimeFormat("en-CA", {
    timeZone: "Europe/Moscow",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hourCycle: "h23",
  }).formatToParts(new Date(value));
  const part = (type: Intl.DateTimeFormatPartTypes) =>
    parts.find((item) => item.type === type)?.value ?? "";
  return `${part("year")}-${part("month")}-${part("day")}T${part("hour")}:${part("minute")}`;
}

export function fromMoscowInput(value: FormDataEntryValue | null): string {
  return new Date(`${String(value)}:00+03:00`).toISOString();
}
