"use client";

import { type ChangeEvent, type FormEvent, useCallback, useEffect, useState } from "react";
import { HomeworkFiles } from "@/components/homework/file-items";
import { authenticatedJson, postAuthenticated } from "@/lib/auth-api";
import { type Homework, homeworkState } from "@/lib/homework";
import { formatMoscow, fromMoscowInput, toMoscowInput } from "@/lib/lessons";
import { uploadPrivateFile } from "@/lib/files";

const accepted = ".pdf,.png,.jpg,.jpeg,.webp,.docx";

export function TeacherHomework({ lessonId }: { lessonId: string }) {
  const [homework, setHomework] = useState<Homework | null>(null);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    const response = await fetch(`/api/v1/teacher/lessons/${lessonId}/homework`, { cache: "no-store" });
    if (!response.ok) throw new Error("Не удалось загрузить домашнее задание");
    setHomework(await response.json() as Homework);
  }, [lessonId]);

  useEffect(() => { load().catch((caught) => setError(caught instanceof Error ? caught.message : "Ошибка загрузки")); }, [load]);

  async function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    const due = data.get("due_at");
    setPending(true);
    setError("");
    try {
      const payload = { description: data.get("description"), due_at: due ? fromMoscowInput(due) : null };
      if (homework?.assignment) {
        await authenticatedJson(`/api/v1/teacher/assignments/${homework.assignment.id}`, "PATCH", { ...payload, version: homework.assignment.version });
      } else {
        await postAuthenticated(`/api/v1/teacher/lessons/${lessonId}/assignment`, payload);
      }
      await load();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Не удалось сохранить задание");
    } finally { setPending(false); }
  }

  async function upload(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    const assignment = homework?.assignment;
    if (!file || !assignment) return;
    setPending(true);
    setError("");
    try {
      await uploadPrivateFile("ASSIGNMENT_MATERIAL", "ASSIGNMENT", assignment.id, file);
      event.target.value = "";
      await load();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Не удалось загрузить материал");
    } finally { setPending(false); }
  }

  async function remove(id: string) {
    setPending(true);
    setError("");
    try {
      await authenticatedJson(`/api/v1/files/${id}`, "DELETE");
      await load();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Не удалось удалить материал");
    } finally { setPending(false); }
  }

  if (homework === null) {
    return <section className="homework-panel"><h3>Домашнее задание</h3>{error ? <p className="form-error" role="alert">{error}</p> : <p className="helper-text">Загрузка…</p>}</section>;
  }

  return <section className="homework-panel">
    <div className="section-heading"><h3>Домашнее задание</h3>{homework ? <span className={`status homework-${homework.state.toLowerCase()}`}>{homeworkState[homework.state]}</span> : null}</div>
    <form className="stack-form" key={homework?.assignment?.version ?? "new"} onSubmit={save}>
      <label>Задание<textarea name="description" rows={4} maxLength={20000} required defaultValue={homework?.assignment?.description ?? ""} /></label>
      <label>Срок по Москве<input name="due_at" type="datetime-local" defaultValue={homework?.assignment?.due_at ? toMoscowInput(homework.assignment.due_at) : ""} /></label>
      <button className="secondary-button" disabled={pending} type="submit">{homework?.assignment ? "Сохранить изменения" : "Создать задание"}</button>
    </form>
    {homework?.assignment ? <div className="homework-files"><h4>Файлы задания</h4><HomeworkFiles items={homework.assignment.files} onRemove={remove} pending={pending} /><label className="secondary-button file-picker">{pending ? "Загрузка…" : "Добавить файл"}<input type="file" accept={accepted} disabled={pending} onChange={upload} /></label></div> : null}
    {homework?.submission ? <div className="submission-view"><h4>Ответ ученика</h4><p className="helper-text">Отправлен {formatMoscow(homework.submission.submitted_at)}</p>{homework.submission.answer_text ? <p>{homework.submission.answer_text}</p> : null}<HomeworkFiles items={homework.submission.files} /></div> : null}
    {error ? <p className="form-error" role="alert">{error}</p> : null}
  </section>;
}
