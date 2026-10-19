"use client";

import { type ChangeEvent, useCallback, useEffect, useState } from "react";
import { authenticatedJson, postAuthenticated, uploadAuthenticated } from "@/lib/auth-api";
import { formatFileSize, type PrivateFile, type UploadTicket } from "@/lib/files";

const accepted = ".pdf,.png,.jpg,.jpeg,.webp,.docx";

export function LessonMaterials({ lessonId, canUpload = false }: { lessonId: string; canUpload?: boolean }) {
  const [items, setItems] = useState<PrivateFile[]>([]);
  const [error, setError] = useState("");
  const [pending, setPending] = useState(false);

  const load = useCallback(async () => {
    const response = await fetch(`/api/v1/files/lesson/${lessonId}`, { cache: "no-store" });
    if (!response.ok) throw new Error("Не удалось загрузить список материалов");
    setItems(await response.json() as PrivateFile[]);
  }, [lessonId]);

  useEffect(() => {
    load().catch((caught) => setError(caught instanceof Error ? caught.message : "Ошибка загрузки"));
  }, [load]);

  async function upload(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    if (!file) return;
    setPending(true);
    setError("");
    try {
      const ticket = await postAuthenticated<UploadTicket>("/api/v1/files/upload-init", {
        purpose: "LESSON_MATERIAL",
        target_type: "LESSON",
        target_id: lessonId,
        original_filename: file.name,
        byte_size: file.size,
      });
      await uploadAuthenticated(ticket.upload_url, file);
      await postAuthenticated<PrivateFile>(`/api/v1/files/upload-complete/${ticket.ticket_id}`);
      await load();
      event.target.value = "";
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Не удалось загрузить файл");
    } finally {
      setPending(false);
    }
  }

  async function remove(id: string) {
    setPending(true);
    setError("");
    try {
      await authenticatedJson(`/api/v1/files/${id}`, "DELETE");
      await load();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Не удалось удалить файл");
    } finally {
      setPending(false);
    }
  }

  return <section className="lesson-materials">
    <h3>Материалы</h3>
    {items.length ? <ul className="file-list">{items.map((item) => <li key={item.id}><a className="text-link" href={item.download_url}>{item.original_filename}</a><small>{formatFileSize(item.byte_size)}</small>{canUpload ? <button className="danger-button compact-button" disabled={pending} type="button" onClick={() => remove(item.id)}>Удалить</button> : null}</li>)}</ul> : <p className="helper-text">Материалов пока нет.</p>}
    {canUpload ? <label className="secondary-button file-picker">{pending ? "Загрузка…" : "Добавить файл"}<input type="file" accept={accepted} disabled={pending} onChange={upload} /></label> : null}
    {error ? <p className="form-error" role="alert">{error}</p> : null}
  </section>;
}
