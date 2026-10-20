import Link from "next/link";
import { groupLessons, type CalendarMarker, moscowDateKey, shiftDate, weekRange } from "@/lib/calendar";
import { type Lesson, lessonStatus } from "@/lib/lessons";

const dayFormatter = new Intl.DateTimeFormat("ru-RU", { weekday: "long", day: "numeric", month: "short", timeZone: "UTC" });
const timeFormatter = new Intl.DateTimeFormat("ru-RU", { hour: "2-digit", minute: "2-digit", timeZone: "Europe/Moscow" });

export function WeekCalendar({ lessons, markers = [], week, basePath, showStudent }: { lessons: Lesson[]; markers?: CalendarMarker[]; week: string; basePath: string; showStudent: boolean }) {
  const range = weekRange(week);
  const grouped = groupLessons(lessons);
  const markerGroups = new Map<string, CalendarMarker[]>();
  for (const marker of markers) {
    const key = moscowDateKey(marker.starts_at);
    markerGroups.set(key, [...(markerGroups.get(key) ?? []), marker]);
  }
  return <section className="management-card calendar-section" aria-labelledby="calendar-title">
    <div className="calendar-heading"><div><p className="eyebrow">Москва · UTC+3</p><h2 id="calendar-title">Неделя с {dayFormatter.format(new Date(`${range.start}T00:00:00Z`))}</h2></div><nav aria-label="Переход между неделями"><Link className="secondary-button" href={`${basePath}?week=${shiftDate(range.start, -7)}`}>Предыдущая</Link><Link className="secondary-button" href={`${basePath}?week=${shiftDate(range.start, 7)}`}>Следующая</Link></nav></div>
    <ol className="calendar-week">
      {range.days.map((day) => <li className="calendar-day" key={day}><h3><time dateTime={day}>{dayFormatter.format(new Date(`${day}T00:00:00Z`))}</time></h3>
        <div className="calendar-events">{(grouped.get(day) ?? []).map((lesson) => <article className={`calendar-event status-${lesson.status.toLowerCase()}`} key={lesson.id}><strong>{timeFormatter.format(new Date(lesson.starts_at))}–{timeFormatter.format(new Date(lesson.ends_at))}</strong><span>{lesson.title}</span>{showStudent ? <small>{lesson.student_name}</small> : null}<small>{lessonStatus[lesson.status]}</small></article>)}{(markerGroups.get(day) ?? []).map((marker) => <div className={`calendar-marker calendar-marker-${marker.tone}`} key={marker.id}><strong>{timeFormatter.format(new Date(marker.starts_at))}–{timeFormatter.format(new Date(marker.ends_at))}</strong><span>{marker.label}</span></div>)}{!(grouped.get(day)?.length || markerGroups.get(day)?.length) ? <span className="calendar-empty">Нет событий</span> : null}</div>
      </li>)}
    </ol>
  </section>;
}
