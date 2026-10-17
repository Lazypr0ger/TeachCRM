import secrets
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import delete, func, select, update
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.modules.auth.models import (
    AuditLog,
    InvitationToken,
    LoginAttempt,
    PasswordResetRequestRecord,
    PasswordResetToken,
    SessionRecord,
    StudentProfile,
    User,
    UserRole,
    UserStatus,
)
from app.modules.auth.schemas import StudentCreateRequest
from app.modules.auth.security import (
    hash_password,
    new_token,
    normalize_login,
    token_hash,
    verify_password,
)

DUMMY_PASSWORD_HASH = hash_password("dummy-password-never-used")


class AuthError(Exception):
    pass


class RateLimitError(AuthError):
    pass


def utc_now() -> datetime:
    return datetime.now(UTC)


def expired(value: datetime, now: datetime) -> bool:
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value <= now


def add_audit(
    db: Session, actor_id: UUID | None, action: str, entity_type: str, entity_id: UUID
) -> None:
    db.add(
        AuditLog(
            actor_user_id=actor_id,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            created_at=utc_now(),
        )
    )


def bootstrap_teacher(db: Session, login: str, password: str) -> User:
    if db.scalar(select(func.count()).select_from(User).where(User.role == UserRole.TEACHER)):
        raise AuthError("Учётная запись преподавателя уже создана")
    normalized = normalize_login(login)
    if db.scalar(select(User).where(func.lower(User.login) == normalized)):
        raise AuthError("Логин уже используется")
    now = utc_now()
    teacher = User(
        role=UserRole.TEACHER,
        login=normalized,
        password_hash=hash_password(password),
        status=UserStatus.ACTIVE,
        activated_at=now,
    )
    db.add(teacher)
    db.flush()
    add_audit(db, teacher.id, "TEACHER_BOOTSTRAPPED", "user", teacher.id)
    db.commit()
    return teacher


def authenticate(db: Session, login: str, password: str) -> User:
    normalized = normalize_login(login)
    login_digest = token_hash(normalized)
    now = utc_now()
    window = now - timedelta(minutes=15)
    attempts = db.scalar(
        select(func.count())
        .select_from(LoginAttempt)
        .where(LoginAttempt.login_hash == login_digest, LoginAttempt.attempted_at >= window)
    )
    if attempts is not None and attempts >= 5:
        raise RateLimitError("Слишком много попыток. Повторите позже")

    user = db.scalar(select(User).where(func.lower(User.login) == normalized))
    password_ok = verify_password(user.password_hash if user else DUMMY_PASSWORD_HASH, password)
    if user is None or not password_ok or user.status != UserStatus.ACTIVE:
        db.add(LoginAttempt(login_hash=login_digest, attempted_at=now))
        db.commit()
        raise AuthError("Неверный логин или пароль")

    db.execute(delete(LoginAttempt).where(LoginAttempt.login_hash == login_digest))
    user.last_login_at = now
    db.commit()
    return user


def create_session(
    db: Session, user: User, settings: Settings, user_agent: str | None
) -> tuple[str, str]:
    now = utc_now()
    raw_session = new_token()
    raw_csrf = new_token()
    record = SessionRecord(
        user_id=user.id,
        token_hash=token_hash(raw_session),
        csrf_hash=token_hash(raw_csrf),
        expires_at=now + timedelta(hours=settings.session_absolute_hours),
        idle_expires_at=now + timedelta(hours=settings.session_idle_hours),
        last_seen_at=now,
        user_agent_hint=(user_agent or "")[:200] or None,
        created_at=now,
    )
    db.add(record)
    db.commit()
    return raw_session, raw_csrf


def revoke_all_sessions(db: Session, user_id: UUID) -> None:
    db.execute(
        update(SessionRecord)
        .where(SessionRecord.user_id == user_id, SessionRecord.revoked_at.is_(None))
        .values(revoked_at=utc_now())
    )


def issue_invitation(db: Session, user_id: UUID, settings: Settings) -> tuple[str, datetime]:
    now = utc_now()
    db.execute(
        update(InvitationToken)
        .where(InvitationToken.user_id == user_id, InvitationToken.used_at.is_(None))
        .values(used_at=now)
    )
    raw = new_token()
    expires_at = now + timedelta(hours=settings.invitation_ttl_hours)
    db.add(
        InvitationToken(
            user_id=user_id,
            token_hash=token_hash(raw),
            expires_at=expires_at,
            created_at=now,
        )
    )
    db.commit()
    return raw, expires_at


def create_student_with_invitation(
    db: Session, payload: StudentCreateRequest, teacher: User, settings: Settings
) -> tuple[StudentProfile, User, str, datetime]:
    login = normalize_login(payload.login or f"student-{secrets.token_hex(4)}")
    if db.scalar(select(User).where(func.lower(User.login) == login)):
        raise AuthError("Логин уже используется")
    user = User(role=UserRole.STUDENT, login=login, status=UserStatus.INVITED)
    db.add(user)
    db.flush()
    profile = StudentProfile(
        user_id=user.id,
        first_name=payload.first_name.strip(),
        last_name=payload.last_name.strip(),
        patronymic=payload.patronymic.strip() if payload.patronymic else None,
        grade=payload.grade,
        active=True,
    )
    db.add(profile)
    db.flush()
    add_audit(db, teacher.id, "STUDENT_CREATED", "student_profile", profile.id)
    db.commit()
    raw, expires_at = issue_invitation(db, user.id, settings)
    return profile, user, raw, expires_at


def activate_invitation(db: Session, raw_token: str, password: str) -> User:
    now = utc_now()
    invitation = db.scalar(
        select(InvitationToken)
        .where(InvitationToken.token_hash == token_hash(raw_token))
        .with_for_update()
    )
    if invitation is None or invitation.used_at is not None or expired(invitation.expires_at, now):
        raise AuthError("Ссылка приглашения недействительна или истекла")
    user = db.get(User, invitation.user_id)
    if user is None or user.status != UserStatus.INVITED:
        raise AuthError("Ссылка приглашения недействительна или истекла")
    user.password_hash = hash_password(password)
    user.status = UserStatus.ACTIVE
    user.activated_at = now
    invitation.used_at = now
    add_audit(db, user.id, "STUDENT_ACTIVATED", "user", user.id)
    db.commit()
    return user


def issue_password_reset(
    db: Session, user: User, actor: User | None, settings: Settings
) -> tuple[str, datetime]:
    now = utc_now()
    db.execute(
        update(PasswordResetToken)
        .where(PasswordResetToken.user_id == user.id, PasswordResetToken.used_at.is_(None))
        .values(used_at=now)
    )
    raw = new_token()
    expires_at = now + timedelta(minutes=settings.password_reset_ttl_minutes)
    db.add(
        PasswordResetToken(
            user_id=user.id,
            token_hash=token_hash(raw),
            expires_at=expires_at,
            created_at=now,
        )
    )
    db.execute(
        update(PasswordResetRequestRecord)
        .where(
            PasswordResetRequestRecord.user_id == user.id,
            PasswordResetRequestRecord.resolved_at.is_(None),
        )
        .values(resolved_at=now)
    )
    add_audit(db, actor.id if actor else None, "PASSWORD_RESET_ISSUED", "user", user.id)
    db.commit()
    return raw, expires_at


def request_password_reset(db: Session, login: str) -> None:
    user = db.scalar(select(User).where(func.lower(User.login) == normalize_login(login)))
    if user is None or user.status != UserStatus.ACTIVE:
        return
    pending = db.scalar(
        select(PasswordResetRequestRecord).where(
            PasswordResetRequestRecord.user_id == user.id,
            PasswordResetRequestRecord.resolved_at.is_(None),
        )
    )
    if pending is None:
        db.add(PasswordResetRequestRecord(user_id=user.id, requested_at=utc_now()))
        db.commit()


def reset_password(db: Session, raw_token: str, password: str) -> User:
    now = utc_now()
    reset = db.scalar(
        select(PasswordResetToken)
        .where(PasswordResetToken.token_hash == token_hash(raw_token))
        .with_for_update()
    )
    if reset is None or reset.used_at is not None or expired(reset.expires_at, now):
        raise AuthError("Ссылка восстановления недействительна или истекла")
    user = db.get(User, reset.user_id)
    if user is None or user.status != UserStatus.ACTIVE:
        raise AuthError("Ссылка восстановления недействительна или истекла")
    user.password_hash = hash_password(password)
    user.version += 1
    reset.used_at = now
    revoke_all_sessions(db, user.id)
    add_audit(db, user.id, "PASSWORD_RESET_COMPLETED", "user", user.id)
    db.commit()
    return user


def suspend_student(db: Session, student_id: UUID, teacher: User) -> None:
    profile = db.get(StudentProfile, student_id)
    if profile is None:
        raise AuthError("Ученик не найден")
    user = db.get(User, profile.user_id)
    if user is None or user.role != UserRole.STUDENT:
        raise AuthError("Ученик не найден")
    user.status = UserStatus.SUSPENDED
    user.version += 1
    profile.active = False
    revoke_all_sessions(db, user.id)
    add_audit(db, teacher.id, "STUDENT_SUSPENDED", "student_profile", profile.id)
    db.commit()
