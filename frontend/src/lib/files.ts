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

export function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} Б`;
  if (bytes < 1024 * 1024) return `${Math.ceil(bytes / 1024)} КБ`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} МБ`;
}
import { postAuthenticated, uploadAuthenticated } from "@/lib/auth-api";


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
