import { formatFileSize, type PrivateFile } from "@/lib/files";

export function HomeworkFiles({
  items,
  onRemove,
  pending = false,
}: {
  items: PrivateFile[];
  onRemove?: (id: string) => void;
  pending?: boolean;
}) {
  if (!items.length) return null;
  return <ul className="file-list">{items.map((item) => <li key={item.id}>
    <a className="text-link" href={item.download_url}>{item.original_filename}</a>
    <small>{formatFileSize(item.byte_size)}</small>
    {onRemove ? <button className="danger-button compact-button" disabled={pending} type="button" onClick={() => onRemove(item.id)}>Удалить</button> : null}
  </li>)}</ul>;
}
