from __future__ import annotations

import os
import re
from pathlib import Path
from uuid import UUID

from fastapi import UploadFile


def sanitize_filename(filename: str) -> str:
    # Keep it filesystem-safe without trying to preserve every unicode char.
    filename = filename.strip().replace("..", ".")
    filename = re.sub(r"[^A-Za-z0-9._-]+", "_", filename)
    return filename[:200] if len(filename) > 200 else filename


async def save_upload_to_disk(
    upload_file: UploadFile,
    upload_dir: str,
    document_id: UUID,
) -> tuple[str, int, str | None]:
    original = upload_file.filename or "upload"
    safe = sanitize_filename(original)

    target_dir = Path(upload_dir) / str(document_id)
    os.makedirs(target_dir, exist_ok=True)

    target_path = target_dir / safe
    size = 0
    with open(target_path, "wb") as f:
        while True:
            chunk = await upload_file.read(1024 * 1024)
            if not chunk:
                break
            f.write(chunk)
            size += len(chunk)

    return str(target_path), size, upload_file.content_type

