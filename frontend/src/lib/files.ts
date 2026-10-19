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
