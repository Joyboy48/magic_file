from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


JobStatus = Literal["queued", "processing", "completed", "failed"]


class DocumentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    original_filename: str
    mime_type: str | None = None
    size_bytes: int
    storage_path: str
    created_at: datetime


class JobOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    document_id: UUID
    status: JobStatus
    attempt: int

    stage: str | None = None
    progress_percent: int = 0

    extracted_json: dict[str, Any] | None = None
    reviewed_json: dict[str, Any] | None = None
    final_json: dict[str, Any] | None = None

    error_message: str | None = None

    created_at: datetime
    updated_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None
    finalized_at: datetime | None = None

    celery_task_id: str | None = None

    document: dict[str, Any] | None = Field(
        default=None, description="Lightweight document info (filename, mime type, size)."
    )


class JobListItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    job: JobOut
    filename: str
    size_bytes: int
    mime_type: str | None = None
    created_at: datetime


class UploadResponse(BaseModel):
    jobs: list[JobListItemOut]


class UpdateReviewedRequest(BaseModel):
    reviewed_json: dict[str, Any]


class ProgressEvent(BaseModel):
    type: str
    job_id: str
    stage: str | None = None
    progress_percent: int | None = None
    timestamp_utc: datetime
    payload: dict[str, Any] = Field(default_factory=dict)

