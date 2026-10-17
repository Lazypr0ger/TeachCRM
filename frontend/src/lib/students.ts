export type Student = {
  id: string;
  user_id: string;
  login: string;
  status: "INVITED" | "ACTIVE" | "SUSPENDED";
  first_name: string;
  last_name: string;
  patronymic: string | null;
  grade: number | null;
  created_at: string;
  activated_at?: string | null;
  last_login_at?: string | null;
  updated_at?: string;
};

export type StudentList = {
  items: Student[];
  total: number;
  page: number;
  page_size: number;
};

export const studentStatus: Record<Student["status"], string> = {
  INVITED: "Ожидает активации",
  ACTIVE: "Активен",
  SUSPENDED: "Заблокирован",
};
