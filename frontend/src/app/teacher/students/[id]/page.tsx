import Link from "next/link";
import { StudentCardForm } from "@/components/teacher/student-card-form";
import { BillingProfileForm } from "@/components/teacher/billing-profile-form";
import { requireRole, serverGet } from "@/lib/server-auth";
import { type Student, studentStatus } from "@/lib/students";

export default async function StudentPage({ params }: { params: Promise<{ id: string }> }) {
  await requireRole("TEACHER");
  const { id } = await params;
  const student = await serverGet<Student>(`/api/v1/teacher/students/${id}`);
  return <main className="management-shell narrow-management">
    <header className="management-header">
      <div><Link className="text-link" href="/teacher/students">← Все ученики</Link><h1>{student.last_name} {student.first_name}</h1><p>{studentStatus[student.status]} · {student.login}</p></div>
    </header>
    <StudentCardForm student={student} />
    <BillingProfileForm studentId={student.id} />
  </main>;
}
