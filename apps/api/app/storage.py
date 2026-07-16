"""Object storage (MinIO). Raw tender files only — parsed truth lives in
Postgres with its grounding, never in loose files."""

import io

from minio import Minio
from minio.error import S3Error

from app.core.config import Settings


class ObjectStorage:
    def __init__(self, settings: Settings) -> None:
        self._client = Minio(
            settings.minio_endpoint,
            access_key=settings.minio_access_key,
            secret_key=settings.minio_secret_key,
            secure=settings.minio_secure,
        )
        self._bucket = settings.minio_bucket_raw

    def _ensure_bucket(self) -> None:
        if not self._client.bucket_exists(self._bucket):
            try:
                self._client.make_bucket(self._bucket)
            except S3Error as error:  # racing creator is fine
                if error.code not in {"BucketAlreadyOwnedByYou", "BucketAlreadyExists"}:
                    raise

    def put_pdf(self, object_key: str, data: bytes) -> None:
        self._ensure_bucket()
        self._client.put_object(
            self._bucket,
            object_key,
            io.BytesIO(data),
            length=len(data),
            content_type="application/pdf",
        )

    def exists(self, object_key: str) -> bool:
        try:
            self._client.stat_object(self._bucket, object_key)
            return True
        except S3Error as error:
            if error.code == "NoSuchKey":
                return False
            raise

    @property
    def bucket(self) -> str:
        return self._bucket
