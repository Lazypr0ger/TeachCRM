import io
import subprocess
from pathlib import Path
from typing import Any

import pytest

from app import ops


class FakeBody(io.BytesIO):
    pass


class FakePaginator:
    def __init__(self, client: "FakeS3") -> None:
        self.client = client

    def paginate(self, *, Bucket: str) -> list[dict[str, Any]]:
        contents = [{"Key": key} for key in sorted(self.client.buckets.get(Bucket, {}))]
        return [{"Contents": contents}] if contents else [{}]


class FakeS3:
    def __init__(self) -> None:
        self.buckets: dict[str, dict[str, tuple[bytes, str]]] = {
            "tutorcrm-private": {"files/example.txt": (b"private material", "text/plain")}
        }

    def get_paginator(self, _name: str) -> FakePaginator:
        return FakePaginator(self)

    def get_object(self, *, Bucket: str, Key: str) -> dict[str, Any]:
        content, content_type = self.buckets[Bucket][Key]
        return {"Body": FakeBody(content), "ContentType": content_type}

    def create_bucket(self, **arguments: Any) -> None:
        self.buckets[arguments["Bucket"]] = {}

    def upload_file(
        self, filename: str, bucket: str, key: str, *, ExtraArgs: dict[str, str]
    ) -> None:
        self.buckets[bucket][key] = (Path(filename).read_bytes(), ExtraArgs["ContentType"])

    def delete_objects(self, *, Bucket: str, Delete: dict[str, Any]) -> None:
        for item in Delete["Objects"]:
            self.buckets[Bucket].pop(item["Key"], None)

    def delete_bucket(self, *, Bucket: str) -> None:
        del self.buckets[Bucket]


def fake_compose(*args: str, stdout: Any = None, stdin_bytes: bytes | None = None) -> Any:
    if "pg_dump" in args:
        stdout.write(b"postgres custom dump")
    if any("SELECT version_num" in argument for argument in args):
        return subprocess.CompletedProcess(args, 0, stdout=b"20261020_0016\n", stderr=b"")
    if "pg_restore" in args:
        assert stdin_bytes == b"postgres custom dump"
    return subprocess.CompletedProcess(args, 0, stdout=b"", stderr=b"")


def test_backup_verify_and_full_rehearsal(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    client = FakeS3()
    monkeypatch.setattr(ops, "s3_client", lambda: client)
    monkeypatch.setattr(ops, "compose", fake_compose)
    archive = ops.create_backup(tmp_path / "snapshot.tar.gz")

    assert archive.stat().st_mode & 0o777 == 0o600
    ops.rehearse_restore(archive)
    assert list(client.buckets) == ["tutorcrm-private"]

    with io.BytesIO(archive.read_bytes()) as stream:
        assert stream.read(2) == b"\x1f\x8b"


def test_verify_rejects_changed_payload(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(ops, "s3_client", lambda: FakeS3())
    monkeypatch.setattr(ops, "compose", fake_compose)
    archive = ops.create_backup(tmp_path / "snapshot.tar.gz")
    extracted = tmp_path / "extracted"
    extracted.mkdir()
    ops.extract_verified(archive, extracted)
    (extracted / "database.dump").write_bytes(b"changed")

    with pytest.raises(ops.OperationsError, match="Контрольная сумма"):
        # Repack the changed directory to exercise archive verification.
        changed = tmp_path / "changed.tar.gz"
        import tarfile

        with tarfile.open(changed, "w:gz") as target:
            for path in extracted.iterdir():
                target.add(path, arcname=path.name)
        ops.extract_verified(changed, tmp_path / "changed-extracted")
