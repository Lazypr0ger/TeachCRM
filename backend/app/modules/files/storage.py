from functools import lru_cache
from typing import Any, Protocol

import boto3  # type: ignore[import-untyped]

from app.core.config import get_settings


class ObjectStorage(Protocol):
    def put(self, key: str, content: bytes, content_type: str) -> None: ...

    def copy(self, source_key: str, destination_key: str, content_type: str) -> None: ...

    def get(self, key: str) -> bytes: ...

    def delete(self, key: str) -> None: ...


class S3ObjectStorage:
    def __init__(self) -> None:
        settings = get_settings()
        self.bucket = settings.s3_bucket
        self.client: Any = boto3.client(
            "s3",
            endpoint_url=settings.s3_endpoint,
            region_name=settings.s3_region,
            aws_access_key_id=settings.s3_access_key,
            aws_secret_access_key=settings.s3_secret_key,
        )

    def put(self, key: str, content: bytes, content_type: str) -> None:
        self.client.put_object(Bucket=self.bucket, Key=key, Body=content, ContentType=content_type)

    def copy(self, source_key: str, destination_key: str, content_type: str) -> None:
        self.client.copy_object(
            Bucket=self.bucket,
            Key=destination_key,
            CopySource={"Bucket": self.bucket, "Key": source_key},
            ContentType=content_type,
            MetadataDirective="REPLACE",
        )

    def get(self, key: str) -> bytes:
        result = self.client.get_object(Bucket=self.bucket, Key=key)
        return bytes(result["Body"].read())

    def delete(self, key: str) -> None:
        self.client.delete_object(Bucket=self.bucket, Key=key)


@lru_cache
def get_storage() -> ObjectStorage:
    return S3ObjectStorage()
