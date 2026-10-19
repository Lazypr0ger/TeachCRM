from typing import Annotated
from urllib.parse import quote
from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, Response, UploadFile, status

from app.core.config import Settings, get_settings
from app.modules.auth.dependencies import CsrfUser, CurrentUser, DbSession
from app.modules.files.schemas import FileResponse, UploadInitRequest, UploadTicketResponse
from app.modules.files.service import (
    FileConflictError,
    FileNotFoundError,
    FilePermissionError,
    FileValidationError,
    complete_upload,
    delete_file,
    get_authorized_file,
    initiate_upload,
    list_lesson_files,
    upload_content,
)
from app.modules.files.storage import ObjectStorage, get_storage

router = APIRouter(prefix="/api/v1/files", tags=["private-files"])
AppSettings = Annotated[Settings, Depends(get_settings)]
Storage = Annotated[ObjectStorage, Depends(get_storage)]


def file_http_error(exc: Exception) -> HTTPException:
    if isinstance(exc, FileNotFoundError):
        code = status.HTTP_404_NOT_FOUND
    elif isinstance(exc, FilePermissionError):
        code = status.HTTP_403_FORBIDDEN
    elif isinstance(exc, FileConflictError):
        code = status.HTTP_409_CONFLICT
    else:
        code = status.HTTP_422_UNPROCESSABLE_CONTENT
    return HTTPException(status_code=code, detail=str(exc))


@router.post(
    "/upload-init", response_model=UploadTicketResponse, status_code=status.HTTP_201_CREATED
)
def upload_init(
    payload: UploadInitRequest,
    user: CsrfUser,
    db: DbSession,
    settings: AppSettings,
) -> UploadTicketResponse:
    try:
        return initiate_upload(db, payload, user, settings)
    except (FileNotFoundError, FilePermissionError, FileValidationError, FileConflictError) as exc:
        raise file_http_error(exc) from exc


@router.post("/upload-tickets/{ticket_id}/content", status_code=status.HTTP_204_NO_CONTENT)
async def upload_ticket_content(
    ticket_id: UUID,
    user: CsrfUser,
    db: DbSession,
    settings: AppSettings,
    storage: Storage,
    file: Annotated[UploadFile, File()],
) -> Response:
    content = await file.read(settings.file_max_bytes + 1)
    try:
        upload_content(db, ticket_id, content, user, settings, storage)
    except (FileNotFoundError, FileConflictError, FileValidationError) as exc:
        raise file_http_error(exc) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/upload-complete/{ticket_id}", response_model=FileResponse)
def upload_complete(
    ticket_id: UUID, user: CsrfUser, db: DbSession, storage: Storage
) -> FileResponse:
    try:
        return complete_upload(db, ticket_id, user, storage)
    except (FileNotFoundError, FilePermissionError, FileValidationError, FileConflictError) as exc:
        raise file_http_error(exc) from exc


@router.get("/lesson/{lesson_id}", response_model=list[FileResponse])
def lesson_files(lesson_id: UUID, user: CurrentUser, db: DbSession) -> list[FileResponse]:
    try:
        return list_lesson_files(db, lesson_id, user)
    except FileNotFoundError as exc:
        raise file_http_error(exc) from exc


@router.get("/{file_id}/download")
def download(file_id: UUID, user: CurrentUser, db: DbSession, storage: Storage) -> Response:
    try:
        item = get_authorized_file(db, file_id, user)
        content = storage.get(item.storage_key)
    except FileNotFoundError as exc:
        raise file_http_error(exc) from exc
    encoded_name = quote(item.original_filename)
    return Response(
        content=content,
        media_type=item.mime_type,
        headers={
            "Content-Disposition": f"attachment; filename*=UTF-8''{encoded_name}",
            "X-Content-Type-Options": "nosniff",
            "Cache-Control": "private, no-store",
        },
    )


@router.delete("/{file_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove(file_id: UUID, user: CsrfUser, db: DbSession, storage: Storage) -> Response:
    try:
        delete_file(db, file_id, user, storage)
    except (FileNotFoundError, FilePermissionError) as exc:
        raise file_http_error(exc) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)
