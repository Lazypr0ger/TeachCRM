import argparse
import hashlib
import json
import os
import shutil
import subprocess
import tarfile
import tempfile
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, cast
from uuid import uuid4

import boto3  # type: ignore[import-untyped]

from app.core.config import get_settings

REPO_ROOT = Path(__file__).resolve().parents[2]
COMPOSE_FILE = REPO_ROOT / "infra" / "compose.dev.yaml"
ARCHIVE_VERSION = 1


class OperationsError(RuntimeError):
    pass


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def compose(
    *args: str, stdout: Any = None, stdin_bytes: bytes | None = None
) -> subprocess.CompletedProcess[bytes]:
    command = ["docker", "compose", "-f", str(COMPOSE_FILE), *args]
    try:
        return subprocess.run(
            command, check=True, input=stdin_bytes, stdout=stdout, stderr=subprocess.PIPE
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        detail = getattr(exc, "stderr", b"") or b""
        raise OperationsError(detail.decode(errors="replace") or str(exc)) from exc


def s3_client() -> Any:
    settings = get_settings()
    inherited_profiles = {
        name: os.environ.pop(name)
        for name in ("AWS_PROFILE", "AWS_DEFAULT_PROFILE")
        if name in os.environ
    }
    try:
        session = boto3.Session(
            region_name=settings.s3_region,
            aws_access_key_id=settings.s3_access_key,
            aws_secret_access_key=settings.s3_secret_key,
        )
        client = session.client("s3", endpoint_url=settings.s3_endpoint)
    finally:
        os.environ.update(inherited_profiles)
    return client


def export_objects(root: Path) -> list[dict[str, Any]]:
    settings = get_settings()
    client = s3_client()
    root.mkdir(parents=True)
    objects: list[dict[str, Any]] = []
    paginator = client.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=settings.s3_bucket):
        for summary in page.get("Contents", []):
            key = str(summary["Key"])
            response = client.get_object(Bucket=settings.s3_bucket, Key=key)
            filename = f"{len(objects):08d}-{hashlib.sha256(key.encode()).hexdigest()}.bin"
            destination = root / filename
            with destination.open("wb") as stream:
                shutil.copyfileobj(response["Body"], stream)
            objects.append(
                {
                    "key": key,
                    "file": f"objects/{filename}",
                    "size": destination.stat().st_size,
                    "sha256": sha256(destination),
                    "content_type": response.get("ContentType") or "application/octet-stream",
                }
            )
    return objects


def write_manifest(root: Path, objects: list[dict[str, Any]]) -> dict[str, Any]:
    settings = get_settings()
    database = root / "database.dump"
    manifest = {
        "format_version": ARCHIVE_VERSION,
        "created_at": datetime.now(UTC).isoformat(),
        "database": {
            "file": "database.dump",
            "size": database.stat().st_size,
            "sha256": sha256(database),
        },
        "storage": {"bucket": settings.s3_bucket, "objects": objects},
    }
    (root / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return manifest


def default_archive_path(directory: Path) -> Path:
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    return directory / f"tutorcrm-{stamp}.tar.gz"


def create_backup(output: Path) -> Path:
    output = output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists():
        raise OperationsError(f"Архив уже существует: {output}")
    running = compose("ps", "--services", "--status", "running", stdout=subprocess.PIPE)
    writable_services = [
        service for service in ("backend", "worker") if service in running.stdout.decode().split()
    ]
    if writable_services:
        compose("stop", *writable_services)
    try:
        with tempfile.TemporaryDirectory(prefix="tutorcrm-backup-") as temp:
            root = Path(temp)
            with (root / "database.dump").open("wb") as stream:
                compose(
                    "exec",
                    "-T",
                    "postgres",
                    "pg_dump",
                    "-U",
                    "tutorcrm",
                    "-d",
                    "tutorcrm",
                    "-Fc",
                    stdout=stream,
                )
            objects = export_objects(root / "objects")
            write_manifest(root, objects)
            temporary = output.with_suffix(output.suffix + ".partial")
            try:
                with tarfile.open(temporary, "w:gz") as archive:
                    archive.add(root / "database.dump", arcname="database.dump")
                    archive.add(root / "manifest.json", arcname="manifest.json")
                    if (root / "objects").exists():
                        archive.add(root / "objects", arcname="objects")
                os.chmod(temporary, 0o600)
                temporary.replace(output)
            finally:
                temporary.unlink(missing_ok=True)
    finally:
        if writable_services:
            compose("start", *writable_services)
    return output


def extract_verified(archive_path: Path, destination: Path) -> dict[str, Any]:
    try:
        with tarfile.open(archive_path, "r:gz") as archive:
            archive.extractall(destination, filter="data")
        manifest = json.loads((destination / "manifest.json").read_text(encoding="utf-8"))
    except (OSError, tarfile.TarError, KeyError, json.JSONDecodeError) as exc:
        raise OperationsError("Архив повреждён или имеет неверный формат") from exc
    if manifest.get("format_version") != ARCHIVE_VERSION:
        raise OperationsError("Неподдерживаемая версия архива")
    manifest = cast(dict[str, Any], manifest)
    entries = [manifest["database"], *manifest["storage"]["objects"]]
    for entry in entries:
        path = (destination / entry["file"]).resolve()
        if destination.resolve() not in path.parents:
            raise OperationsError("Архив содержит небезопасный путь")
        if (
            not path.is_file()
            or path.stat().st_size != entry["size"]
            or sha256(path) != entry["sha256"]
        ):
            raise OperationsError(f"Контрольная сумма не совпала: {entry['file']}")
    return manifest


def verify_storage_copy(
    client: Any, bucket: str, objects: list[dict[str, Any]], root: Path
) -> None:
    for entry in objects:
        response = client.get_object(Bucket=bucket, Key=entry["key"])
        digest = hashlib.sha256(response["Body"].read()).hexdigest()
        if digest != entry["sha256"]:
            raise OperationsError(f"Проверка объекта не пройдена: {entry['key']}")


def upload_objects(client: Any, bucket: str, objects: list[dict[str, Any]], root: Path) -> None:
    for entry in objects:
        client.upload_file(
            str(root / entry["file"]),
            bucket,
            entry["key"],
            ExtraArgs={"ContentType": entry["content_type"]},
        )


def empty_bucket(client: Any, bucket: str) -> None:
    paginator = client.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=bucket):
        objects = [{"Key": item["Key"]} for item in page.get("Contents", [])]
        if objects:
            client.delete_objects(Bucket=bucket, Delete={"Objects": objects})


def create_bucket(client: Any, bucket: str) -> None:
    region = get_settings().s3_region
    arguments: dict[str, Any] = {"Bucket": bucket}
    if region != "us-east-1":
        arguments["CreateBucketConfiguration"] = {"LocationConstraint": region}
    client.create_bucket(**arguments)


def rehearse_restore(archive_path: Path) -> None:
    database_name = f"tutorcrm_restore_{uuid4().hex[:12]}"
    bucket_name = f"tutorcrm-restore-{uuid4().hex[:12]}"
    client = s3_client()
    with tempfile.TemporaryDirectory(prefix="tutorcrm-restore-") as temp:
        root = Path(temp)
        manifest = extract_verified(archive_path, root)
        compose("exec", "-T", "postgres", "createdb", "-U", "tutorcrm", database_name)
        try:
            compose(
                "exec",
                "-T",
                "postgres",
                "pg_restore",
                "-U",
                "tutorcrm",
                "-d",
                database_name,
                stdin_bytes=(root / manifest["database"]["file"]).read_bytes(),
            )
            result = compose(
                "exec",
                "-T",
                "postgres",
                "psql",
                "-U",
                "tutorcrm",
                "-d",
                database_name,
                "-Atc",
                "SELECT version_num FROM alembic_version",
                stdout=subprocess.PIPE,
            )
            if not result.stdout.strip():
                raise OperationsError("В восстановленной базе отсутствует версия миграции")
            create_bucket(client, bucket_name)
            upload_objects(client, bucket_name, manifest["storage"]["objects"], root)
            verify_storage_copy(client, bucket_name, manifest["storage"]["objects"], root)
        finally:
            compose(
                "exec",
                "-T",
                "postgres",
                "dropdb",
                "-U",
                "tutorcrm",
                "--force",
                "--if-exists",
                database_name,
            )
            try:
                empty_bucket(client, bucket_name)
                client.delete_bucket(Bucket=bucket_name)
            except Exception:
                pass


def restore_backup(archive_path: Path, confirmation: str, safety_directory: Path) -> Path:
    if confirmation != "RESTORE-tutorcrm":
        raise OperationsError("Для восстановления укажите --confirm RESTORE-tutorcrm")
    safety = create_backup(default_archive_path(safety_directory))
    client = s3_client()
    settings = get_settings()
    with tempfile.TemporaryDirectory(prefix="tutorcrm-restore-") as temp:
        root = Path(temp)
        manifest = extract_verified(archive_path, root)
        compose("stop", "backend", "worker", "frontend")
        try:
            compose(
                "exec",
                "-T",
                "postgres",
                "dropdb",
                "-U",
                "tutorcrm",
                "--force",
                "--if-exists",
                "tutorcrm",
            )
            compose("exec", "-T", "postgres", "createdb", "-U", "tutorcrm", "tutorcrm")
            compose(
                "exec",
                "-T",
                "postgres",
                "pg_restore",
                "-U",
                "tutorcrm",
                "-d",
                "tutorcrm",
                stdin_bytes=(root / manifest["database"]["file"]).read_bytes(),
            )
            empty_bucket(client, settings.s3_bucket)
            upload_objects(client, settings.s3_bucket, manifest["storage"]["objects"], root)
            verify_storage_copy(client, settings.s3_bucket, manifest["storage"]["objects"], root)
            compose("up", "-d", "migrate", "backend", "worker", "frontend")
        except Exception as exc:
            raise OperationsError(f"Восстановление прервано. Страховочный архив: {safety}") from exc
    return safety


def prune_backups(directory: Path, keep_days: int) -> int:
    cutoff = datetime.now(UTC) - timedelta(days=keep_days)
    removed = 0
    for path in directory.glob("tutorcrm-*.tar.gz"):
        modified = datetime.fromtimestamp(path.stat().st_mtime, UTC)
        if modified < cutoff:
            path.unlink()
            removed += 1
    return removed


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description="Резервное копирование Tutor CRM")
    subcommands = result.add_subparsers(dest="command", required=True)
    backup = subcommands.add_parser("backup", help="Создать архив PostgreSQL и S3")
    backup.add_argument("--output", type=Path)
    backup.add_argument("--directory", type=Path, default=REPO_ROOT / "backups")
    backup.add_argument("--keep-days", type=int, default=14)
    verify = subcommands.add_parser("verify", help="Проверить архив без восстановления")
    verify.add_argument("archive", type=Path)
    rehearsal = subcommands.add_parser("rehearse", help="Восстановить во временные DB и bucket")
    rehearsal.add_argument("archive", type=Path)
    restore = subcommands.add_parser("restore", help="Восстановить рабочие DB и bucket")
    restore.add_argument("archive", type=Path)
    restore.add_argument("--confirm", required=True)
    restore.add_argument("--safety-directory", type=Path, default=REPO_ROOT / "backups")
    return result


def main() -> None:
    args = parser().parse_args()
    if args.command == "backup":
        if args.keep_days < 1:
            raise SystemExit("--keep-days должен быть положительным")
        output = args.output or default_archive_path(args.directory)
        created = create_backup(output)
        removed = prune_backups(created.parent, args.keep_days)
        print(f"Создан архив: {created} (удалено старых: {removed})")
    elif args.command == "verify":
        with tempfile.TemporaryDirectory(prefix="tutorcrm-verify-") as temp:
            manifest = extract_verified(args.archive.resolve(), Path(temp))
        print(f"Архив исправен: {len(manifest['storage']['objects'])} объектов")
    elif args.command == "rehearse":
        rehearse_restore(args.archive.resolve())
        print("Тестовое восстановление PostgreSQL и S3 прошло успешно")
    else:
        safety = restore_backup(args.archive.resolve(), args.confirm, args.safety_directory)
        print(f"Восстановление завершено. Страховочный архив: {safety}")


if __name__ == "__main__":
    main()
