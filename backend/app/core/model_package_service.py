from __future__ import annotations

import ast
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import shutil
import stat
import subprocess
import sys
from tempfile import TemporaryDirectory
from typing import Any
from uuid import uuid4
from zipfile import BadZipFile, ZipFile, ZipInfo

from app.core.model_catalog import ModelCatalogService
from app.core.model_registry import ModelRegistryService
from app.core.model_sync import ModelSyncService
from app.core.settings import Settings


ALLOWED_TASK_TYPES = {"fault_diagnosis", "rul_prediction", "anomaly_detection"}
REQUIRED_FILES = {"README.md", "model_card.json", "config.yaml", "inference.py", "requirements.txt"}
SUPPORTED_SAMPLE_SUFFIXES = {".csv", ".npy", ".npz", ".mat"}
SAFE_IDENTIFIER = re.compile(r"^[a-z0-9][a-z0-9_.-]{1,79}$")


class ModelPackageError(RuntimeError):
    """Raised when a managed model package cannot advance safely."""


class ModelPackageService:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.littlemodel_root = settings.resolved_littlemodel_root
        self.registry = ModelRegistryService(self.littlemodel_root)
        self.catalog = ModelCatalogService(settings.database_path)
        self.staging_root = settings.model_package_staging_path
        self.managed_root = self.littlemodel_root / "managed_models"
        self.trash_root = settings.model_package_trash_path
        self.staging_root.mkdir(parents=True, exist_ok=True)
        self.managed_root.mkdir(parents=True, exist_ok=True)
        self.trash_root.mkdir(parents=True, exist_ok=True)

    def create_upload(self, filename: str, content: bytes) -> dict[str, Any]:
        if not filename.lower().endswith(".zip"):
            raise ModelPackageError("Only .zip model packages are supported.")
        if not content:
            raise ModelPackageError("Uploaded model package is empty.")
        if len(content) > self.settings.model_package_max_upload_bytes:
            raise ModelPackageError("Uploaded model package exceeds the configured size limit.")

        upload_id = uuid4().hex
        upload_dir = self.staging_root / upload_id
        archive_path = upload_dir / "package.zip"
        extracted_dir = upload_dir / "extracted"
        upload_dir.mkdir(parents=True)
        archive_path.write_bytes(content)

        try:
            self._safe_extract(archive_path, extracted_dir)
            package_dir = self._find_package_dir(extracted_dir)
            inspection = self._inspect_package(package_dir)
            metadata = {
                "upload_id": upload_id,
                "filename": Path(filename).name,
                "sha256": hashlib.sha256(content).hexdigest(),
                "size_bytes": len(content),
                "status": "inspected",
                "created_at": _utcnow(),
                "updated_at": _utcnow(),
                "package_relative_path": package_dir.relative_to(upload_dir).as_posix(),
                "inspection": inspection,
                "validation": None,
                "published_model_version_id": None,
            }
            self._write_metadata(upload_dir, metadata)
            return metadata
        except Exception:
            shutil.rmtree(upload_dir, ignore_errors=True)
            raise

    def get_upload(self, upload_id: str) -> dict[str, Any]:
        return self._read_metadata(self._upload_dir(upload_id))

    def update_metadata(self, upload_id: str, updates: dict[str, Any]) -> dict[str, Any]:
        upload_dir = self._upload_dir(upload_id)
        metadata = self._read_metadata(upload_dir)
        if metadata["status"] == "published":
            raise ModelPackageError("Published package metadata can no longer be edited.")
        package_dir = upload_dir / metadata["package_relative_path"]
        model_card_path = package_dir / "model_card.json"
        model_card = json.loads(model_card_path.read_text(encoding="utf-8"))
        for key in ("model_name", "description", "dataset"):
            value = updates.get(key)
            if value is not None:
                model_card[key] = str(value).strip()
        if updates.get("limitations") is not None:
            model_card["limitations"] = [str(item).strip() for item in updates["limitations"] if str(item).strip()]
        model_card_path.write_text(json.dumps(model_card, indent=2, ensure_ascii=False), encoding="utf-8")
        metadata["inspection"] = self._inspect_package(package_dir)
        metadata["status"] = "inspected"
        metadata["validation"] = None
        metadata["updated_at"] = _utcnow()
        self._write_metadata(upload_dir, metadata)
        return metadata

    def validate_upload(self, upload_id: str) -> dict[str, Any]:
        upload_dir = self._upload_dir(upload_id)
        metadata = self._read_metadata(upload_dir)
        package_dir = upload_dir / metadata["package_relative_path"]
        inspection = self._inspect_package(package_dir)
        sample_path = self._find_sample(package_dir)
        entrypoint = str(inspection["model_card"]["adapter_entrypoint"])

        with TemporaryDirectory(dir=upload_dir) as temporary_dir:
            temp_path = Path(temporary_dir)
            result_path = temp_path / "probe_result.json"
            output_dir = temp_path / "outputs"
            probe_path = Path(__file__).with_name("model_package_probe.py")
            try:
                completed = subprocess.run(
                    [
                        sys.executable,
                        str(probe_path),
                        str(package_dir),
                        entrypoint,
                        str(sample_path),
                        str(output_dir),
                        str(result_path),
                    ],
                    cwd=package_dir,
                    capture_output=True,
                    text=True,
                    timeout=self.settings.model_validation_timeout_seconds,
                    check=False,
                )
            except subprocess.TimeoutExpired as exc:
                raise ModelPackageError(
                    f"Model smoke test timed out after {self.settings.model_validation_timeout_seconds:g} seconds."
                ) from exc
            if completed.returncode != 0:
                error = (completed.stderr or completed.stdout or "unknown model execution error").strip()
                raise ModelPackageError(f"Model smoke test failed: {error[-2000:]}")
            if not result_path.exists():
                raise ModelPackageError("Model smoke test did not produce a JSON result.")
            result = json.loads(result_path.read_text(encoding="utf-8"))

        validation = {
            "status": "passed",
            "validated_at": _utcnow(),
            "sample_path": sample_path.relative_to(package_dir).as_posix(),
            "result_keys": sorted(result.keys()),
            "result_status": result.get("status"),
            "stdout": completed.stdout[-2000:],
        }
        metadata["inspection"] = inspection
        metadata["validation"] = validation
        metadata["status"] = "validated"
        metadata["updated_at"] = _utcnow()
        self._write_metadata(upload_dir, metadata)
        return metadata

    def publish_upload(self, upload_id: str) -> dict[str, Any]:
        upload_dir = self._upload_dir(upload_id)
        metadata = self._read_metadata(upload_dir)
        if metadata["status"] != "validated":
            raise ModelPackageError("The model package must pass validation before publication.")
        card = metadata["inspection"]["model_card"]
        model_id = card["model_id"]
        version = card["model_version"]
        task_type = card["task_type"]
        package_dir = upload_dir / metadata["package_relative_path"]
        destination = self.managed_root / task_type / model_id / version
        if destination.exists():
            raise ModelPackageError(f"Published model directory already exists: {destination}")

        registry_payload = self.registry.load_registry()
        if any(item.get("model_id") == model_id for item in registry_payload["models"]):
            raise ModelPackageError(f"A registered model already uses model_id '{model_id}'.")

        destination.parent.mkdir(parents=True, exist_ok=True)
        temporary_destination = destination.parent / f".{version}.{upload_id}.tmp"
        shutil.copytree(package_dir, temporary_destination)
        temporary_destination.replace(destination)

        entry = {
            "model_id": model_id,
            "family_code": card.get("family_code") or model_id,
            "task_type": task_type,
            "model_dir": destination.relative_to(self.littlemodel_root).as_posix(),
            "entrypoint": card["adapter_entrypoint"],
            "status": "candidate",
        }
        original_registry = json.loads(json.dumps(registry_payload))
        registry_payload["models"].append(entry)
        try:
            self._write_registry(registry_payload)
            ModelSyncService(
                self.settings.database_path,
                self.littlemodel_root,
                default_alias=self.settings.model_catalog_default_alias,
            ).sync_registry()
        except Exception:
            self._write_registry(original_registry)
            shutil.rmtree(destination, ignore_errors=True)
            raise

        metadata["status"] = "published"
        metadata["updated_at"] = _utcnow()
        metadata["published_model_version_id"] = f"model_version::{model_id}"
        metadata["published_model_dir"] = entry["model_dir"]
        self._write_metadata(upload_dir, metadata)
        return metadata

    def archive_version(self, model_version_id: str) -> dict[str, Any]:
        version = self._get_managed_version(model_version_id)
        if version.get("aliases"):
            raise ModelPackageError("Remove default/champion/canary/fallback aliases before archiving this model.")
        registry_payload = self.registry.load_registry()
        original_registry = json.loads(json.dumps(registry_payload))
        model_id = str(version["legacy_model_id"])
        matching_entry = next((entry for entry in registry_payload["models"] if entry.get("model_id") == model_id), None)
        if matching_entry is None:
            raise ModelPackageError(f"Registry entry does not exist for model_id '{model_id}'.")
        matching_entry["status"] = "archived"
        try:
            self._write_registry(registry_payload)
            self._sync_catalog()
        except Exception:
            self._write_registry(original_registry)
            raise
        return self.catalog.get_model_version_detail(model_version_id) or {}

    def delete_version(self, model_version_id: str) -> dict[str, Any]:
        version = self._get_managed_version(model_version_id)
        if version.get("aliases"):
            raise ModelPackageError("Remove model aliases before deleting this model.")
        with self.catalog.database.connect() as connection:
            count_row = connection.execute(
                "SELECT COUNT(*) AS count FROM diagnosis_cases WHERE model_version_id = ?",
                (model_version_id,),
            ).fetchone()
        if count_row and int(count_row["count"]) > 0:
            raise ModelPackageError("This model has diagnosis history and must be archived instead of deleted.")

        model_dir = (self.littlemodel_root / str(version["model_dir"])).resolve()
        trash_destination = self.trash_root / f"{version['legacy_model_id']}__{uuid4().hex}"
        registry_payload = self.registry.load_registry()
        original_registry = json.loads(json.dumps(registry_payload))
        model_id = str(version["legacy_model_id"])
        remaining_entries = [entry for entry in registry_payload["models"] if entry.get("model_id") != model_id]
        if len(remaining_entries) == len(registry_payload["models"]):
            raise ModelPackageError(f"Registry entry does not exist for model_id '{model_id}'.")
        shutil.move(str(model_dir), str(trash_destination))
        try:
            registry_payload["models"] = remaining_entries
            self._write_registry(registry_payload)
            self._sync_catalog()
        except Exception:
            self._write_registry(original_registry)
            model_dir.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(trash_destination), str(model_dir))
            raise
        return {"status": "deleted", "model_version_id": model_version_id, "trash_path": str(trash_destination)}

    def discard_upload(self, upload_id: str) -> None:
        upload_dir = self._upload_dir(upload_id)
        metadata = self._read_metadata(upload_dir)
        if metadata["status"] == "published":
            raise ModelPackageError("Published uploads cannot be discarded from staging history.")
        shutil.rmtree(upload_dir)

    def _safe_extract(self, archive_path: Path, destination: Path) -> None:
        try:
            with ZipFile(archive_path) as archive:
                members = archive.infolist()
                if not members or len(members) > self.settings.model_package_max_files:
                    raise ModelPackageError("Model package has an invalid number of files.")
                total_size = sum(member.file_size for member in members)
                if total_size > self.settings.model_package_max_uncompressed_bytes:
                    raise ModelPackageError("Uncompressed model package exceeds the configured size limit.")
                for member in members:
                    self._validate_zip_member(member)
                archive.extractall(destination)
        except BadZipFile as exc:
            raise ModelPackageError("Uploaded file is not a valid ZIP archive.") from exc

    def _validate_zip_member(self, member: ZipInfo) -> None:
        path = PurePosixPath(member.filename.replace("\\", "/"))
        if path.is_absolute() or ".." in path.parts:
            raise ModelPackageError(f"Unsafe path in ZIP archive: {member.filename}")
        unix_mode = member.external_attr >> 16
        if unix_mode and stat.S_ISLNK(unix_mode):
            raise ModelPackageError(f"Symbolic links are not allowed: {member.filename}")

    def _find_package_dir(self, extracted_dir: Path) -> Path:
        cards = [path for path in extracted_dir.rglob("model_card.json") if len(path.relative_to(extracted_dir).parts) <= 3]
        if len(cards) != 1:
            raise ModelPackageError("Model package must contain exactly one model_card.json near the ZIP root.")
        return cards[0].parent

    def _inspect_package(self, package_dir: Path) -> dict[str, Any]:
        missing = sorted(name for name in REQUIRED_FILES if not (package_dir / name).is_file())
        if not (package_dir / "weights").is_dir():
            missing.append("weights/")
        if not (package_dir / "test_data").is_dir():
            missing.append("test_data/")
        if missing:
            raise ModelPackageError(f"Model package is missing required paths: {missing}")
        if not any(path.is_file() for path in (package_dir / "weights").rglob("*")):
            raise ModelPackageError("weights/ must contain at least one model artifact.")

        try:
            card = json.loads((package_dir / "model_card.json").read_text(encoding="utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise ModelPackageError(f"model_card.json is invalid: {exc}") from exc
        if not isinstance(card, dict):
            raise ModelPackageError("model_card.json must contain a JSON object.")
        required_card_fields = {"model_id", "model_name", "model_version", "task_type", "adapter_entrypoint", "input_contract"}
        missing_fields = sorted(field for field in required_card_fields if not card.get(field))
        if missing_fields:
            raise ModelPackageError(f"model_card.json is missing required fields: {missing_fields}")
        if not isinstance(card["input_contract"], dict):
            raise ModelPackageError("model_card.json field 'input_contract' must be a JSON object.")
        for field in ("model_id", "model_version"):
            if not SAFE_IDENTIFIER.fullmatch(str(card[field])):
                raise ModelPackageError(f"model_card.json field '{field}' contains unsafe characters.")
        family_code = card.get("family_code")
        if family_code and not SAFE_IDENTIFIER.fullmatch(str(family_code)):
            raise ModelPackageError("model_card.json field 'family_code' contains unsafe characters.")
        if card["task_type"] not in ALLOWED_TASK_TYPES:
            raise ModelPackageError(f"Unsupported task_type: {card['task_type']}")
        if card["adapter_entrypoint"] != "inference.py:predict":
            raise ModelPackageError("adapter_entrypoint must be 'inference.py:predict'.")

        inference_path = package_dir / "inference.py"
        try:
            syntax_tree = ast.parse(inference_path.read_text(encoding="utf-8"))
        except (SyntaxError, UnicodeDecodeError) as exc:
            raise ModelPackageError(f"inference.py cannot be parsed: {exc}") from exc
        if not any(isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == "predict" for node in syntax_tree.body):
            raise ModelPackageError("inference.py must define a top-level predict function.")

        sample = self._find_sample(package_dir)
        requirements = [
            line.strip()
            for line in (package_dir / "requirements.txt").read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.lstrip().startswith("#")
        ]
        return {
            "model_card": card,
            "entrypoint": card["adapter_entrypoint"],
            "sample_path": sample.relative_to(package_dir).as_posix(),
            "weight_files": [path.relative_to(package_dir).as_posix() for path in (package_dir / "weights").rglob("*") if path.is_file()],
            "requirements": requirements,
            "requirements_installation": "disabled",
            "warnings": ["Model code is only intended for trusted administrator-managed packages."],
        }

    def _find_sample(self, package_dir: Path) -> Path:
        samples = sorted(
            path for path in (package_dir / "test_data").rglob("*")
            if path.is_file() and path.suffix.lower() in SUPPORTED_SAMPLE_SUFFIXES
        )
        if not samples:
            raise ModelPackageError("test_data/ must contain a .csv, .npy, .npz or .mat smoke-test sample.")
        return samples[0]

    def _get_managed_version(self, model_version_id: str) -> dict[str, Any]:
        version = self.catalog.get_model_version_detail(model_version_id)
        if version is None:
            raise ModelPackageError(f"Model version does not exist: {model_version_id}")
        model_dir = (self.littlemodel_root / str(version["model_dir"])).resolve()
        try:
            model_dir.relative_to(self.managed_root.resolve())
        except ValueError as exc:
            raise ModelPackageError("Built-in model versions cannot be removed through package management.") from exc
        if not model_dir.exists():
            raise ModelPackageError(f"Managed model directory does not exist: {model_dir}")
        return version

    def _write_registry(self, payload: dict[str, Any]) -> None:
        temporary_path = self.registry.registry_path.with_suffix(".json.tmp")
        temporary_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        temporary_path.replace(self.registry.registry_path)

    def _sync_catalog(self) -> None:
        ModelSyncService(
            self.settings.database_path,
            self.littlemodel_root,
            default_alias=self.settings.model_catalog_default_alias,
        ).sync_registry()

    def _upload_dir(self, upload_id: str) -> Path:
        if not re.fullmatch(r"[a-f0-9]{32}", upload_id):
            raise ModelPackageError("Invalid upload identifier.")
        upload_dir = self.staging_root / upload_id
        if not upload_dir.is_dir():
            raise ModelPackageError(f"Model package upload does not exist: {upload_id}")
        return upload_dir

    def _read_metadata(self, upload_dir: Path) -> dict[str, Any]:
        metadata_path = upload_dir / "metadata.json"
        if not metadata_path.exists():
            raise ModelPackageError(f"Model package metadata does not exist: {upload_dir.name}")
        return json.loads(metadata_path.read_text(encoding="utf-8"))

    def _write_metadata(self, upload_dir: Path, metadata: dict[str, Any]) -> None:
        (upload_dir / "metadata.json").write_text(
            json.dumps(metadata, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()
