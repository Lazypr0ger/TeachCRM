"use client";

import { type ChangeEvent, type FormEvent, useCallback, useEffect, useRef, useState } from "react";
import { HomeworkFiles } from "@/components/homework/file-items";
import { authenticatedJson, postAuthenticated } from "@/lib/auth-api";
import { formatFileSize, uploadPrivateFile, validateFileSelection } from "@/lib/files";
import { type Homework, type HomeworkSubmission, homeworkState } from "@/lib/homework";
import { formatMoscow } from "@/lib/lessons";

const accepted = ".pdf,.png,.jpg,.jpeg,.webp,.docx";

type PendingFile = {
  id: string;
  file: File;
  status: "pending" | "uploading" | "uploaded" | "error";
  uploadedId?: string;
};

export function StudentHomework({ lessonId }: { lessonId: string }) {
  const [homework, setHomework] = useState<Homework | null>(null);
  const [pending, setPending] = useState(false);
  const [selectedFiles, setSelectedFiles] = useState<PendingFile[]>([]);
  const [error, setError] = useState("");
  const [requestId] = useState(() => crypto.randomUUID());
  const submitLock = useRef(false);

  const load = useCallback(async () => {
    const response = await fetch(`/api/v1/student/lessons/${lessonId}/homework`, { cache: "no-store" });
    if (!response.ok) throw new Error("Не удалось загрузить домашнее задание");
    setHomework(await response.json() as Homework);
  }, [lessonId]);

  useEffect(() => { load().catch((caught) => setError(caught instanceof Error ? caught.message : "Ошибка загрузки")); }, [load]);

  function selectFiles(event: ChangeEvent<HTMLInputElement>) {
    const files = Array.from(event.target.files ?? []);
    event.target.value = "";
    if (!files.length) return;
    setError("");
    const validationError = validateFileSelection(
      files,
      (homework?.draft_files.length ?? 0) + selectedFiles.length,
    );
    if (validationError) {
      setError(validationError);
      return;
    }
    setSelectedFiles((current) => [
      ...current,
      ...files.map((file) => ({
        id: crypto.randomUUID(),
        file,
        status: "pending" as const,
      })),
    ]);
  }

  async function removeSelected(item: PendingFile) {
    if (item.uploadedId) await authenticatedJson(`/api/v1/files/${item.uploadedId}`, "DELETE");
    setSelectedFiles((current) => current.filter((candidate) => candidate.id !== item.id));
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
    if (!homework?.assignment || submitLock.current) return;
    if (!window.confirm("Отправить окончательный ответ? После отправки изменить его нельзя.")) return;
    submitLock.current = true;
    const data = new FormData(event.currentTarget);
    setPending(true);
    setError("");
    try {
      const uploadedIds: string[] = [];
      for (const item of selectedFiles) {
        if (item.uploadedId) {
          uploadedIds.push(item.uploadedId);
          continue;
        }
        setSelectedFiles((current) => current.map((candidate) => candidate.id === item.id
          ? { ...candidate, status: "uploading" }
          : candidate));
        try {
          const uploaded = await uploadPrivateFile("HOMEWORK", "ASSIGNMENT", homework.assignment.id, item.file);
          uploadedIds.push(uploaded.id);
          setSelectedFiles((current) => current.map((candidate) => candidate.id === item.id
            ? { ...candidate, status: "uploaded", uploadedId: uploaded.id }
            : candidate));
        } catch (caught) {
          setSelectedFiles((current) => current.map((candidate) => candidate.id === item.id
            ? { ...candidate, status: "error" }
            : candidate));
          throw caught;
        }
      }
      await postAuthenticated<HomeworkSubmission>(`/api/v1/student/assignments/${homework.assignment.id}/submission`, {
        answer_text: data.get("answer_text") || null,
        file_ids: [...homework.draft_files.map((file) => file.id), ...uploadedIds],
        idempotency_key: requestId,
      });
      setSelectedFiles([]);
      await load();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Не удалось отправить ответ");
    } finally {
      submitLock.current = false;
      setPending(false);
    }
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
      {selectedFiles.length ? <ul className="file-list pending-file-list">{selectedFiles.map((item) => <li key={item.id}>
        <span>{item.file.name}</span>
        <small>{formatFileSize(item.file.size)} · {{ pending: "готов к отправке", uploading: "загрузка…", uploaded: "загружен", error: "ошибка — повторите отправку" }[item.status]}</small>
        <button className="danger-button compact-button" disabled={pending} type="button" onClick={() => removeSelected(item).catch((caught) => setError(caught instanceof Error ? caught.message : "Не удалось удалить файл"))}>Удалить</button>
      </li>)}</ul> : null}
      <label className="secondary-button file-picker">Приложить файлы<input type="file" accept={accepted} multiple disabled={pending} onChange={selectFiles} /></label>
      <p className="helper-text">PDF, PNG, JPG, WEBP или DOCX · до 15 МБ на файл · до 10 файлов</p>
      <button className="primary-button" disabled={pending} type="submit">Отправить окончательно</button>
    </form>}
    {error ? <p className="form-error" role="alert">{error}</p> : null}
  </section>;
}
