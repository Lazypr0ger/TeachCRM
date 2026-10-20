from datetime import UTC, timedelta
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.modules.auth.models import StudentProfile
from app.modules.auth.service import utc_now
from app.modules.billing.models import Invoice, PaymentClaim
from app.modules.homework.models import Assignment, HomeworkSubmission
from app.modules.lessons.models import Lesson, LessonStatus
from app.modules.lessons.schemas import TeacherDashboardResponse
from app.modules.lessons.service import lesson_response
from app.modules.scheduling.models import RescheduleRequest, RescheduleStatus


def teacher_dashboard(db: Session, teacher_id: UUID, timezone: str) -> TeacherDashboardResponse:
    now = utc_now()
    local_start = now.astimezone(ZoneInfo(timezone)).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    start = local_start.astimezone(UTC)
    end = (local_start + timedelta(days=1)).astimezone(UTC)

    today_rows = db.execute(
        select(Lesson, StudentProfile)
        .join(StudentProfile, StudentProfile.id == Lesson.student_id)
        .where(
            Lesson.teacher_id == teacher_id,
            Lesson.starts_at >= start,
            Lesson.starts_at < end,
            Lesson.status != LessonStatus.CANCELLED,
        )
        .order_by(Lesson.starts_at)
    ).all()
    lessons = [lesson_response(lesson, profile) for lesson, profile in today_rows]

    next_row = db.execute(
        select(Lesson, StudentProfile)
        .join(StudentProfile, StudentProfile.id == Lesson.student_id)
        .where(
            Lesson.teacher_id == teacher_id,
            Lesson.status == LessonStatus.SCHEDULED,
            Lesson.ends_at > now,
        )
        .order_by(Lesson.starts_at)
        .limit(1)
    ).one_or_none()

    pending_claims = db.scalar(
        select(func.count())
        .select_from(PaymentClaim)
        .join(Invoice, Invoice.id == PaymentClaim.invoice_id)
        .where(
            PaymentClaim.status == "PENDING",
            select(Lesson.id)
            .where(Lesson.student_id == Invoice.student_id, Lesson.teacher_id == teacher_id)
            .exists(),
        )
    ) or 0
    homework_today = db.scalar(
        select(func.count())
        .select_from(HomeworkSubmission)
        .join(Assignment, Assignment.id == HomeworkSubmission.assignment_id)
        .join(Lesson, Lesson.id == Assignment.lesson_id)
        .where(
            Lesson.teacher_id == teacher_id,
            HomeworkSubmission.submitted_at >= start,
            HomeworkSubmission.submitted_at < end,
        )
    ) or 0
    pending_reschedules = db.scalar(
        select(func.count())
        .select_from(RescheduleRequest)
        .join(Lesson, Lesson.id == RescheduleRequest.lesson_id)
        .where(
            Lesson.teacher_id == teacher_id,
            RescheduleRequest.status.in_(
                (RescheduleStatus.PENDING, RescheduleStatus.COUNTER_OFFER)
            ),
        )
    ) or 0

    return TeacherDashboardResponse(
        today_lessons=lessons,
        next_lesson=lesson_response(*next_row) if next_row else None,
        lessons_today=len(lessons),
        pending_payment_claims=pending_claims,
        homework_submissions_today=homework_today,
        pending_reschedule_requests=pending_reschedules,
    )
