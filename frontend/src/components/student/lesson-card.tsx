import { formatMoscow, type Lesson, lessonStatus } from "@/lib/lessons";

export function StudentLessonCard({ lesson, compact = false }: { lesson: Lesson; compact?: boolean }) {
  return <article className="lesson-card">
    <div className="lesson-card-heading"><div><p className="eyebrow">{formatMoscow(lesson.starts_at)}</p><h2>{lesson.title}</h2></div><span className={`status status-${lesson.status.toLowerCase()}`}>{lessonStatus[lesson.status]}</span></div>
    {!compact && lesson.description ? <p>{lesson.description}</p> : null}
    {lesson.status === "SCHEDULED" ? lesson.join_url ? <a className="primary-link" href={lesson.join_url} target="_blank" rel="noreferrer">Подключиться</a> : <p>Ссылка появится позже.</p> : null}
  </article>;
}
