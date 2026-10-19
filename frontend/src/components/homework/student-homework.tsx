"use client";

import { type ChangeEvent, type FormEvent, useCallback, useEffect, useState } from "react";
import { HomeworkFiles } from "@/components/homework/file-items";
import { authenticatedJson, postAuthenticated } from "@/lib/auth-api";
import { uploadPrivateFile } from "@/lib/files";
import { type Homework, type HomeworkSubmission, homeworkState } from "@/lib/homework";
import { formatMoscow } from "@/lib/lessons";

const accepted = ".pdf,.png,.jpg,.jpeg,.webp,.docx";

export function StudentHomework({ lessonId }: { lessonId: string }) {
  const [homework, setHomework] = useState<Homework | null>(null);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState("");
  const [requestId] = useState(() => crypto.randomUUID());

  const load = useCallback(async () => {
    const response = await fetch(`/api/v1/student/lessons/${lessonId}/homework`, { cache: "no-store" });
    if (!response.ok) throw new Error("Не удалось загрузить домашнее задание");
    setHomework(await response.json() as Homework);
  }, [lessonId]);

  useEffect(() => { load().catch((caught) => setError(caught instanceof Error ? caught.message : "Ошибка загрузки")); }, [load]);

  async function upload(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    const assignment = homework?.assignment;
    if (!file || !assignment) return;
    setPending(true);
    setError("");
    try {
      await uploadPrivateFile("HOMEWORK", "ASSIGNMENT", assignment.id, file);
      event.target.value = "";
      await load();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Не удалось загрузить файл");
    } finally { setPending(false); }
  }

  async function remove(id: string) {
    setPending(true);
    try {
      await authenticatedJson(`/api/v1/files/${id}`, "DELETE");
      await load();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Не удалось удалить файл");
    } finally { setPending(false); }
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!homework?.assignment) return;
    if (!window.confirm("Отправить окончательный ответ? После отправки изменить его нельзя.")) return;
    const data = new FormData(event.currentTarget);
    setPending(true);
    setError("");
    try {
      await postAuthenticated<HomeworkSubmission>(`/api/v1/student/assignments/${homework.assignment.id}/submission`, {
        answer_text: data.get("answer_text") || null,
        file_ids: homework.draft_files.map((file) => file.id),
        idempotency_key: requestId,
      });
      await load();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Не удалось отправить ответ");
    } finally { setPending(false); }
  }

  if (!homework) return error ? <p className="form-error" role="alert">{error}</p> : null;
  if (homework.state === "NO_HOMEWORK" || !homework.assignment) return null;
  return <section className="homework-panel">
    <div className="section-heading"><h3>Домашнее задание</h3><span className={`status homework-${homework.state.toLowerCase()}`}>{homeworkState[homework.state]}</span></div>
    <p>{homework.assignment.description}</p>
    {homework.assignment.due_at ? <p className="helper-text">Сдать до {formatMoscow(homework.assignment.due_at)}</p> : null}
    <HomeworkFiles items={homework.assignment.files} />
    {homework.submission ? <div className="submission-view"><h4>Ваш ответ</h4>{homework.submission.answer_text ? <p>{homework.submission.answer_text}</p> : null}<HomeworkFiles items={homework.submission.files} /></div> : <form className="stack-form" onSubmit={submit}>
      <label>Ответ<textarea name="answer_text" rows={4} maxLength={20000} placeholder="Напишите ответ или приложите файл" /></label>
      <HomeworkFiles items={homework.draft_files} onRemove={remove} pending={pending} />
      <label className="secondary-button file-picker">{pending ? "Загрузка…" : "Приложить файл"}<input type="file" accept={accepted} disabled={pending} onChange={upload} /></label>
      <button className="primary-button" disabled={pending} type="submit">Отправить окончательно</button>
    </form>}
    {error ? <p className="form-error" role="alert">{error}</p> : null}
  </section>;
}
