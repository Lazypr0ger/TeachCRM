export type PrivateFile = {
  id: string;
  original_filename: string;
  mime_type: string;
  byte_size: number;
  purpose: "LESSON_MATERIAL" | "ASSIGNMENT_MATERIAL" | "HOMEWORK";
  checksum_sha256: string;
  created_at: string;
  download_url: string;
};

export type UploadTicket = {
  ticket_id: string;
  upload_url: string;
  expires_at: string;
  max_bytes: number;
};

export const FILE_MAX_BYTES = 15 * 1024 * 1024;
export const FILE_MAX_PER_TARGET = 10;
const allowedExtension = /\.(pdf|png|jpe?g|webp|docx)$/i;

export type FileCandidate = Pick<File, "name" | "size">;

export function validateFileSelection(files: FileCandidate[], existingCount: number): string | null {
  if (existingCount + files.length > FILE_MAX_PER_TARGET) {
    return `К одному ответу можно приложить не больше ${FILE_MAX_PER_TARGET} файлов`;
  }
  const invalidType = files.find((file) => !allowedExtension.test(file.name));
  if (invalidType) return `Файл «${invalidType.name}» имеет неподдерживаемый формат`;
  const invalidSize = files.find((file) => file.size < 1 || file.size > FILE_MAX_BYTES);
  if (invalidSize) return `Размер файла «${invalidSize.name}» должен быть от 1 байта до 15 МБ`;
  return null;
}

export function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} Б`;
  if (bytes < 1024 * 1024) return `${Math.ceil(bytes / 1024)} КБ`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} МБ`;
}
import { postAuthenticated, uploadAuthenticated } from "./auth-api";


export async function uploadPrivateFile(
  purpose: PrivateFile["purpose"],
  targetType: "LESSON" | "ASSIGNMENT" | "SUBMISSION",
  targetId: string,
  file: File,
): Promise<PrivateFile> {
  const ticket = await postAuthenticated<UploadTicket>("/api/v1/files/upload-init", {
    purpose,
    target_type: targetType,
    target_id: targetId,
    original_filename: file.name,
    byte_size: file.size,
  });
  await uploadAuthenticated(ticket.upload_url, file);
  return postAuthenticated<PrivateFile>(`/api/v1/files/upload-complete/${ticket.ticket_id}`);
}
