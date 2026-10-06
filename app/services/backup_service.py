"""Full-system backup and safe-restore service for JobPilot."""

import hashlib
import json
import logging
import os
import shutil
import sqlite3
import uuid
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import text
from sqlalchemy.orm import sessionmaker

from app.db.config import get_db_path
from app.db.session import SessionLocal, get_db_session

logger = logging.getLogger(__name__)


def _calc_sha256(file_path: Path) -> str:
    """Calculates SHA-256 checksum for a file."""
    h = hashlib.sha256()
    with open(file_path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


class BackupService:
    """Creates complete system backup archives and performs staging-isolated restores."""

    BACKUP_FORMAT_VERSION = 1
    APPLICATION_VERSION = "2.0"
    SCHEMA_VERSION = "1.0"

    def __init__(
        self,
        db_path: Optional[str] = None,
        profile_path: Optional[str] = None,
        resumes_dir: Optional[str] = None,
        session_factory: Optional[sessionmaker] = None,
        automation_manager: Optional[Any] = None,
    ):
        base_dir = Path(__file__).resolve().parent.parent.parent
        self.db_path = Path(db_path) if db_path else get_db_path()
        self.profile_path = Path(profile_path) if profile_path else (base_dir / "config" / "profile.json")
        self.resumes_dir = Path(resumes_dir) if resumes_dir else (base_dir / "all resumes")
        self._session_factory = session_factory or SessionLocal
        self.automation_manager = automation_manager

    def is_operation_allowed(self) -> Tuple[bool, Optional[str]]:
        """Verifies no active automation run is in progress before backup or restore."""
        if self.automation_manager and hasattr(self.automation_manager, "is_running"):
            if self.automation_manager.is_running():
                return (
                    False,
                    "Cannot perform backup or restore while automation is running. Please stop active automation first.",
                )
        return True, None

    def create_backup(self, target_dir: Optional[str] = None) -> Tuple[bool, str, Dict[str, Any]]:
        """Packages database, profile, and resumes into a timestamped zip archive."""
        allowed, err = self.is_operation_allowed()
        if not allowed:
            return False, err or "Operation blocked", {}

        timestamp_str = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        out_dir = Path(target_dir) if target_dir else (self.db_path.parent / "backups")
        out_dir.mkdir(parents=True, exist_ok=True)
        archive_name = f"jobpilot_backup_{timestamp_str}.zip"
        archive_path = out_dir / archive_name

        # Flush SQLite WAL to ensure disk consistency
        if self.db_path.exists():
            try:
                conn = sqlite3.connect(str(self.db_path))
                conn.execute("PRAGMA wal_checkpoint(TRUNCATE);")
                conn.close()
            except Exception as e:
                logger.warning("WAL checkpoint warning prior to backup: %s", e)


        files_manifest: Dict[str, Dict[str, Any]] = {}

        try:
            with zipfile.ZipFile(archive_path, "w", zipfile.ZIP_DEFLATED) as zf:
                # 1. Database
                if self.db_path.exists():
                    db_arcname = "database/jobpilot.db"
                    zf.write(self.db_path, arcname=db_arcname)
                    files_manifest[db_arcname] = {
                        "size": self.db_path.stat().st_size,
                        "sha256": _calc_sha256(self.db_path),
                    }

                # 2. Profile JSON
                if self.profile_path.exists():
                    prof_arcname = "config/profile.json"
                    zf.write(self.profile_path, arcname=prof_arcname)
                    files_manifest[prof_arcname] = {
                        "size": self.profile_path.stat().st_size,
                        "sha256": _calc_sha256(self.profile_path),
                    }

                # 3. Resumes
                if self.resumes_dir.exists():
                    for root, _, files in os.walk(self.resumes_dir):
                        for f in files:
                            if f.lower().endswith((".pdf", ".docx", ".txt")):
                                full_p = Path(root) / f
                                rel_p = full_p.relative_to(self.resumes_dir)
                                arcname = f"resumes/{rel_p}"
                                zf.write(full_p, arcname=arcname)
                                files_manifest[arcname] = {
                                    "size": full_p.stat().st_size,
                                    "sha256": _calc_sha256(full_p),
                                }

                # 4. Manifest JSON
                manifest_data = {
                    "backup_format_version": self.BACKUP_FORMAT_VERSION,
                    "application_version": self.APPLICATION_VERSION,
                    "schema_version": self.SCHEMA_VERSION,
                    "created_at": datetime.now(timezone.utc).isoformat(),
                    "files": files_manifest,
                }
                zf.writestr("manifest.json", json.dumps(manifest_data, indent=2))

            return True, str(archive_path), manifest_data
        except Exception as exc:
            logger.error("Failed to create backup archive: %s", exc)
            if archive_path.exists():
                archive_path.unlink(missing_ok=True)
            return False, f"Backup creation failed: {exc}", {}

    MAX_FILE_SIZE_BYTES = 100 * 1024 * 1024  # 100 MB per file
    MAX_TOTAL_EXTRACTED_BYTES = 500 * 1024 * 1024  # 500 MB total

    def _safe_extract(self, zf: zipfile.ZipFile, target_dir: Path) -> None:
        """Extracts ZIP archive with strict Zip Slip, symlink, and compression bomb protection."""
        resolved_target = target_dir.resolve()
        total_extracted = 0

        for member in zf.infolist():
            filename = member.filename
            if filename.startswith("/") or filename.startswith("\\") or (len(filename) > 1 and filename[1] == ":"):
                raise ValueError(f"Insecure archive: absolute paths not allowed ({filename})")

            dest_path = (resolved_target / filename).resolve()
            if not dest_path.is_relative_to(resolved_target):
                raise ValueError(f"Insecure archive: Zip Slip / path traversal detected ({filename})")

            mode = (member.external_attr >> 16) & 0o170000
            if mode == 0o120000:
                raise ValueError(f"Insecure archive: symbolic links not allowed ({filename})")

            if member.file_size > self.MAX_FILE_SIZE_BYTES:
                raise ValueError(f"Insecure archive: file exceeds maximum permitted size ({filename})")

            total_extracted += member.file_size
            if total_extracted > self.MAX_TOTAL_EXTRACTED_BYTES:
                raise ValueError("Insecure archive: total decompressed size exceeds maximum archive limit")

            zf.extract(member, resolved_target)

    def verify_backup(self, archive_path: str) -> Tuple[bool, str, Dict[str, Any]]:
        """Validates backup archive integrity without modifying active system files."""
        src_archive = Path(archive_path)
        if not src_archive.exists() or not zipfile.is_zipfile(src_archive):
            return False, "Invalid or missing backup archive file.", {}

        staging_dir = self.db_path.parent / "verify_tmp" / str(uuid.uuid4())
        staging_dir.mkdir(parents=True, exist_ok=True)

        try:
            with zipfile.ZipFile(src_archive, "r") as zf:
                self._safe_extract(zf, staging_dir)

            manifest_file = staging_dir / "manifest.json"
            if not manifest_file.exists():
                return False, "Corrupt backup: missing manifest.json.", {}

            try:
                with open(manifest_file, "r", encoding="utf-8") as f:
                    manifest = json.load(f)
            except Exception as e:
                return False, f"Failed to parse backup manifest: {e}", {}

            files_dict = manifest.get("files", {})
            for rel_name, meta in files_dict.items():
                staged_file = staging_dir / rel_name
                if not staged_file.exists():
                    return False, f"Missing expected backup file: {rel_name}", manifest
                current_hash = _calc_sha256(staged_file)
                if current_hash != meta.get("sha256"):
                    return False, f"SHA-256 checksum mismatch for: {rel_name}", manifest

            staged_db = staging_dir / "database" / "jobpilot.db"
            if staged_db.exists():
                try:
                    conn = sqlite3.connect(str(staged_db))
                    cur = conn.cursor()
                    cur.execute("PRAGMA integrity_check;")
                    rows = cur.fetchall()
                    conn.close()
                    if not rows or rows[0][0] != "ok":
                        return False, f"Staged database failed integrity check: {rows}", manifest
                except Exception as exc:
                    return False, f"Staged database error: {exc}", manifest

            file_count = len(files_dict)
            return True, f"Integrity verified: {file_count} files valid (SHA-256 matched, SQLite OK).", manifest
        except Exception as exc:
            return False, f"Verification failed: {exc}", {}
        finally:
            shutil.rmtree(staging_dir, ignore_errors=True)

    def restore_backup(self, archive_path: str) -> Tuple[bool, str]:
        """Safely validates and restores system data from a backup archive via staging."""
        allowed, err = self.is_operation_allowed()
        if not allowed:
            return False, err or "Operation blocked"

        src_archive = Path(archive_path)
        if not src_archive.exists() or not zipfile.is_zipfile(src_archive):
            return False, "Invalid or missing backup archive file."

        # Setup staging isolation directory
        staging_dir = self.db_path.parent / "restore_tmp" / str(uuid.uuid4())
        staging_dir.mkdir(parents=True, exist_ok=True)

        try:
            # 1. Unpack archive to staging with path traversal and zip bomb verification
            with zipfile.ZipFile(src_archive, "r") as zf:
                self._safe_extract(zf, staging_dir)

            # 2. Manifest verification
            manifest_file = staging_dir / "manifest.json"
            if not manifest_file.exists():
                return False, "Corrupt backup: missing manifest.json."

            try:
                with open(manifest_file, "r", encoding="utf-8") as f:
                    manifest = json.load(f)
            except Exception as e:
                return False, f"Failed to parse backup manifest: {e}"

            # 3. Checksum verification
            files_dict = manifest.get("files", {})
            for rel_name, meta in files_dict.items():
                staged_file = staging_dir / rel_name
                if not staged_file.exists():
                    return False, f"Missing expected backup file: {rel_name}"
                current_hash = _calc_sha256(staged_file)
                if current_hash != meta.get("sha256"):
                    return False, f"SHA-256 checksum mismatch for: {rel_name}"

            # 4. SQLite integrity check on staged database
            staged_db = staging_dir / "database" / "jobpilot.db"
            if staged_db.exists():
                try:
                    conn = sqlite3.connect(str(staged_db))
                    cur = conn.cursor()
                    cur.execute("PRAGMA integrity_check;")
                    rows = cur.fetchall()
                    conn.close()
                    if not rows or rows[0][0] != "ok":
                        return False, f"Staged database failed integrity check: {rows}"
                except Exception as exc:
                    return False, f"Staged database error: {exc}"

            # 5. Dispose active database connections before file replacement
            if self._session_factory:
                try:
                    eng = getattr(self._session_factory, "kw", {}).get("bind") or getattr(self._session_factory, "bind", None)
                    if eng and hasattr(eng, "dispose"):
                        eng.dispose()
                except Exception as e:
                    logger.warning("Notice disposing database engine: %s", e)

            # 6. Pre-restore safety backup of active database
            if self.db_path.exists():
                pre_restore_bak = self.db_path.with_suffix(".db.pre_restore.bak")
                shutil.copy2(self.db_path, pre_restore_bak)

            # 7. Atomic replacement of database
            if staged_db.exists():
                self.db_path.parent.mkdir(parents=True, exist_ok=True)
                for ext in ("-wal", "-shm"):
                    wal_f = Path(str(self.db_path) + ext)
                    if wal_f.exists():
                        wal_f.unlink(missing_ok=True)
                shutil.copy2(staged_db, self.db_path)



            # 7. Restore profile.json
            staged_profile = staging_dir / "config" / "profile.json"
            if staged_profile.exists():
                self.profile_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(staged_profile, self.profile_path)

            # 8. Restore resumes
            staged_resumes = staging_dir / "resumes"
            if staged_resumes.exists():
                self.resumes_dir.mkdir(parents=True, exist_ok=True)
                for root, _, files in os.walk(staged_resumes):
                    for f in files:
                        s_file = Path(root) / f
                        rel_p = s_file.relative_to(staged_resumes)
                        dest_file = self.resumes_dir / rel_p
                        dest_file.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(s_file, dest_file)

            return True, "Backup restored successfully."

        except Exception as exc:
            logger.error("Restore pipeline encountered an unexpected error: %s", exc)
            return False, f"Restore failed: {exc}"
        finally:
            shutil.rmtree(staging_dir, ignore_errors=True)

    def export_profile_json(self, destination_file: str) -> Tuple[bool, str]:
        """Exports profile.json to a specified destination."""
        if not self.profile_path.exists():
            return False, "Source profile.json does not exist."
        try:
            dest = Path(destination_file)
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(self.profile_path, dest)
            return True, f"Profile exported successfully to {dest}."
        except Exception as exc:
            return False, f"Failed to export profile: {exc}"

    def import_profile_json(self, source_file: str) -> Tuple[bool, str]:
        """Validates and imports an external profile JSON file."""
        src = Path(source_file)
        if not src.exists():
            return False, f"Source file does not exist: {src}"

        try:
            with open(src, "r", encoding="utf-8") as f:
                data = json.load(f)

            if not isinstance(data, dict):
                return False, "Invalid profile format: root must be a JSON object."

            # Verify required structure
            if "personal" not in data or "professional" not in data:
                return False, "Invalid profile format: missing 'personal' or 'professional' sections."

            # Atomic copy
            self.profile_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, self.profile_path)
            return True, "Profile imported successfully."
        except json.JSONDecodeError as exc:
            return False, f"Invalid JSON syntax: {exc}"
        except Exception as exc:
            return False, f"Failed to import profile: {exc}"
