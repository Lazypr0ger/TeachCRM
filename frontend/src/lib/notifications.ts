export type NotificationItem = {
  id: string;
  type: string;
  title: string;
  body: string;
  target_type: string | null;
  target_id: string | null;
  read_at: string | null;
  created_at: string;
};

export type NotificationPage = {
  items: NotificationItem[];
  total: number;
  page: number;
  page_size: number;
};

export function notificationTarget(
  item: NotificationItem,
  role: "STUDENT" | "TEACHER",
): string | null {
  if (item.target_type === "LESSON") {
    return role === "STUDENT" ? "/student/lessons" : "/teacher/schedule";
  }
  if (item.target_type === "RESCHEDULE_REQUEST") {
    return role === "STUDENT" ? "/student/schedule" : "/teacher/schedule";
  }
  if (item.target_type === "INVOICE" || item.target_type === "PAYMENT_CLAIM") {
    return role === "STUDENT" ? "/student/billing" : "/teacher/finances";
  }
  if (item.target_type === "TRIAL_REQUEST" && role === "TEACHER") {
    return "/teacher/trials";
  }
  return null;
}
