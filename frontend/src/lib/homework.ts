import type { PrivateFile } from "@/lib/files";

export type Assignment = {
  id: string;
  lesson_id: string;
  description: string;
  due_at: string | null;
  version: number;
  created_at: string;
  updated_at: string;
  files: PrivateFile[];
};

export type HomeworkSubmission = {
  id: string;
  assignment_id: string;
  answer_text: string | null;
  submitted_at: string;
  files: PrivateFile[];
};

export type Homework = {
  state: "NO_HOMEWORK" | "NEEDS_RESPONSE" | "ACCEPTED";
  assignment: Assignment | null;
  submission: HomeworkSubmission | null;
  draft_files: PrivateFile[];
};

export type StudentHomeworkSummary = {
  lesson_id: string;
  lesson_title: string;
  lesson_starts_at: string;
  state: Homework["state"];
  assignment_description: string | null;
  due_at: string | null;
  submitted_at: string | null;
};

export const homeworkState: Record<Homework["state"], string> = {
  NO_HOMEWORK: "Без домашнего задания",
  NEEDS_RESPONSE: "Ожидает ответа",
  ACCEPTED: "Ответ отправлен",
};
