"use client";

import { useState } from "react";
import { StudentCardForm } from "@/components/teacher/student-card-form";
import { StudentPrivacyActions } from "@/components/teacher/student-privacy-actions";
import type { Student } from "@/lib/students";

export function StudentEditDrawer({ student }: { student: Student }) {
  const [open, setOpen] = useState(false);
  return <>
    <button className="primary-button" type="button" onClick={() => setOpen(true)}>Редактировать</button>
    {open ? <div className="drawer-backdrop">
      <aside className="right-drawer" role="dialog" aria-modal="true" aria-labelledby="student-edit-title">
        <header className="drawer-header"><div><p className="eyebrow">Карточка ученика</p><h2 id="student-edit-title">Редактирование</h2></div><button className="secondary-button compact-button" type="button" onClick={() => setOpen(false)}>Закрыть</button></header>
        <div className="drawer-content"><StudentCardForm student={student} /><StudentPrivacyActions studentId={student.id} login={student.login} /></div>
      </aside>
    </div> : null}
  </>;
}
