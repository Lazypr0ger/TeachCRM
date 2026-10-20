export type TrialStatus =
  | "NEW"
  | "IN_REVIEW"
  | "RESCHEDULE_REQUESTED"
  | "CONFIRMED"
  | "COMPLETED"
  | "REJECTED"
  | "CANCELLED";

export type TrialRequest = {
  id: string;
  name: string;
  grade: number;
  goal: string | null;
  preferred_start: string | null;
  preferred_end: string | null;
  confirmed_start: string | null;
  confirmed_end: string | null;
  comment: string | null;
  source: "WEB" | "TELEGRAM";
  status: TrialStatus;
  possible_existing_student: boolean;
  converted_student_id: string | null;
  version: number;
  created_at: string;
  updated_at: string;
};

export type TrialPage = {
  items: TrialRequest[];
  total: number;
  page: number;
  page_size: number;
};

export type PublicSite = {
  brand_name: string;
  tagline: string | null;
  about_text: string | null;
  directions: string[];
  advantages: string[];
  confirmed_results: string[];
  pricing_text: string | null;
  privacy_text: string | null;
  trials_enabled: boolean;
  timezone: string;
};

export type TeacherSiteSettings = PublicSite & {
  configured_trials_enabled: boolean;
  trial_feature_available: boolean;
  version: number;
  updated_at: string | null;
};

export const trialStatus: Record<TrialStatus, string> = {
  NEW: "Новая",
  IN_REVIEW: "На рассмотрении",
  RESCHEDULE_REQUESTED: "Нужно другое время",
  CONFIRMED: "Подтверждена",
  COMPLETED: "Проведена",
  REJECTED: "Отклонена",
  CANCELLED: "Отменена",
};
