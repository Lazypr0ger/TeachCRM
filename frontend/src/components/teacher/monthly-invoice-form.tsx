"use client";

import { type FormEvent, useState } from "react";
import { useRouter } from "next/navigation";
import { postAuthenticated } from "@/lib/auth-api";
import type { Invoice } from "@/lib/billing";
import type { Student } from "@/lib/students";

export function MonthlyInvoiceForm({ students }: { students: Student[] }) {
  const router = useRouter();
  const now = new Date();
  const [pending, setPending] = useState(false);
  const [error, setError] = useState("");

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    setPending(true);
    setError("");
    try {
      await postAuthenticated<Invoice>("/api/v1/teacher/invoices/monthly", {
        student_id: data.get("student_id"), year: Number(data.get("year")), month: Number(data.get("month")),
      });
      router.refresh();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Не удалось создать начисление");
    } finally { setPending(false); }
  }

  return <form className="lesson-form" onSubmit={submit}><label>Ученик<select name="student_id" required>{students.map((student) => <option value={student.id} key={student.id}>{student.last_name} {student.first_name}</option>)}</select></label><label>Год<input name="year" type="number" min="2020" max="2100" defaultValue={now.getFullYear()} required /></label><label>Месяц<input name="month" type="number" min="1" max="12" defaultValue={now.getMonth() + 1} required /></label><button className="primary-button" disabled={pending || !students.length} type="submit">Выпустить помесячное начисление</button>{error ? <p className="form-error wide-field" role="alert">{error}</p> : null}</form>;
}
