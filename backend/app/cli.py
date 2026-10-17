import argparse
import getpass
import os

from sqlalchemy import func, select

from app.core.config import get_settings
from app.core.db import create_db_engine, create_session_factory
from app.modules.auth.models import User
from app.modules.auth.security import normalize_login
from app.modules.auth.service import AuthError, bootstrap_teacher, issue_password_reset


def password_from_environment_or_prompt() -> str:
    password = os.getenv("TUTORCRM_BOOTSTRAP_PASSWORD") or getpass.getpass("Новый пароль: ")
    if len(password) < 12:
        raise SystemExit("Пароль должен содержать не менее 12 символов")
    return password


def main() -> None:
    parser = argparse.ArgumentParser(description="Tutor CRM administration")
    subparsers = parser.add_subparsers(dest="command", required=True)
    bootstrap = subparsers.add_parser("bootstrap-teacher")
    bootstrap.add_argument("--login", required=True)
    reset = subparsers.add_parser("issue-password-reset")
    reset.add_argument("--login", required=True)
    args = parser.parse_args()

    settings = get_settings()
    factory = create_session_factory(create_db_engine(settings.database_url))
    with factory() as db:
        if args.command == "bootstrap-teacher":
            try:
                user = bootstrap_teacher(db, args.login, password_from_environment_or_prompt())
            except AuthError as exc:
                raise SystemExit(str(exc)) from exc
            print(f"Преподаватель создан: {user.login}")
            return

        reset_user = db.scalar(
            select(User).where(func.lower(User.login) == normalize_login(args.login))
        )
        if reset_user is None:
            raise SystemExit("Пользователь не найден")
        raw, expires_at = issue_password_reset(db, reset_user, None, settings)
        print(f"{settings.app_base_url}/reset-password?token={raw}")
        print(f"Ссылка действует до {expires_at.isoformat()}")


if __name__ == "__main__":
    main()
