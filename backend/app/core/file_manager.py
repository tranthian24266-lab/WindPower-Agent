from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from fastapi import UploadFile


class FileManagerError(RuntimeError):
    """Raised when file upload or lookup fails."""


class FileManagerService:
    allowed_suffixes = {".csv", ".mat", ".npy", ".npz"}

    def __init__(self, uploads_root: Path):
        self.uploads_root = Path(uploads_root)
        self.uploads_root.mkdir(parents=True, exist_ok=True)

    async def save_upload(self, upload_file: UploadFile) -> dict[str, Any]:
        filename = Path(upload_file.filename or "").name
        if not filename:
            raise FileManagerError("Uploaded file must include a filename.")

        suffix = Path(filename).suffix.lower()
        if suffix not in self.allowed_suffixes:
            raise FileManagerError(
                f"Unsupported file type '{suffix}'. Supported types: {', '.join(sorted(self.allowed_suffixes))}."
            )

        file_id = uuid4().hex
        file_dir = self.uploads_root / file_id
        file_dir.mkdir(parents=True, exist_ok=False)
        stored_path = file_dir / filename

        content = await upload_file.read()
        stored_path.write_bytes(content)

        metadata = {
            "file_id": file_id,
            "original_filename": filename,
            "stored_path": str(stored_path),
            "suffix": suffix,
            "content_type": upload_file.content_type,
            "size_bytes": int(len(content)),
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        self._metadata_path(file_id).write_text(json.dumps(metadata, indent=2, ensure_ascii=False), encoding="utf-8")
        return metadata

    def import_local_file(self, source_path: Path) -> dict[str, Any]:
        resolved = Path(source_path)
        if not resolved.exists():
            raise FileManagerError(f"Local file does not exist: {resolved}")
        filename = resolved.name
        suffix = resolved.suffix.lower()
        if suffix not in self.allowed_suffixes:
            raise FileManagerError(
                f"Unsupported file type '{suffix}'. Supported types: {', '.join(sorted(self.allowed_suffixes))}."
            )
        file_id = uuid4().hex
        file_dir = self.uploads_root / file_id
        file_dir.mkdir(parents=True, exist_ok=False)
        stored_path = file_dir / filename
        stored_path.write_bytes(resolved.read_bytes())
        metadata = {
            "file_id": file_id,
            "original_filename": filename,
            "stored_path": str(stored_path),
            "suffix": suffix,
            "content_type": None,
            "size_bytes": int(stored_path.stat().st_size),
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        self._metadata_path(file_id).write_text(json.dumps(metadata, indent=2, ensure_ascii=False), encoding="utf-8")
        return metadata

    def get_file_metadata(self, file_id: str) -> dict[str, Any]:
        metadata_path = self._metadata_path(file_id)
        if not metadata_path.exists():
            raise FileManagerError(f"File metadata does not exist for file_id '{file_id}'.")

        try:
            payload = json.loads(metadata_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise FileManagerError(f"Failed to parse file metadata for file_id '{file_id}': {exc}") from exc

        if not isinstance(payload, dict):
            raise FileManagerError(f"Unexpected file metadata structure for file_id '{file_id}'.")
        return payload

    def _metadata_path(self, file_id: str) -> Path:
        return self.uploads_root / file_id / "metadata.json"
