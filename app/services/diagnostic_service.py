"""Sanitized diagnostic reporting service for JobPilot Private Beta.

Generates comprehensive, secret-sanitized diagnostic reports for troubleshooting
and telemetry without leaking credentials, cookies, tokens, or personal secrets.
"""

import json
import logging
import os
import platform
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.db.config import DatabaseConfig
from app.db.session import SessionLocal, get_db_session
from app.services.os.app_paths import AppPaths
from app.services.sanitizer_service import LogSanitizer
from app.version import RELEASE_CHANNEL, VERSION

logger = logging.getLogger(__name__)


class DiagnosticService:
    """Collects system, database, automation, and platform health telemetry into a sanitized report."""

    def __init__(self, session_factory=None):
        self._session_factory = session_factory or SessionLocal

    def generate_report(self) -> Dict[str, Any]:
        """Gathers diagnostic data across all subsystems and runs it through LogSanitizer."""
        now = datetime.now(timezone.utc)
        report: Dict[str, Any] = {
            "metadata": {
                "generated_at_utc": now.isoformat(),
                "application": "JobPilot",
                "version": VERSION,
                "release_channel": RELEASE_CHANNEL,
            },
            "system": self._collect_system_info(),
            "storage_paths": self._collect_storage_paths(),
            "database": self._collect_database_stats(),
            "ai_configuration": self._collect_ai_config(),
            "platforms": self._collect_platform_states(),
            "workspace_readiness": self._collect_readiness_summary(),
            "recent_diagnostic_logs": self._collect_recent_logs(),
        }

        # Final recursive sanitization pass to guarantee 0 leaked secrets
        return LogSanitizer.sanitize_dict(report)

    def generate_markdown(self) -> str:
        """Renders the diagnostic data into a structured Markdown document."""
        data = self.generate_report()
        meta = data.get("metadata", {})
        sys_info = data.get("system", {})
        paths = data.get("storage_paths", {})
        db_info = data.get("database", {})
        ai_info = data.get("ai_configuration", {})
        platforms = data.get("platforms", {})
        readiness = data.get("workspace_readiness", {})
        logs = data.get("recent_diagnostic_logs", [])

        md_lines = [
            "# JobPilot Diagnostic Report",
            f"*Generated at (UTC): {meta.get('generated_at_utc')}*",
            f"**Version**: `{meta.get('version')}` (`{meta.get('release_channel')}`)\n",
            "---",
            "## 1. System & Runtime Environment",
            f"- **OS**: {sys_info.get('os')} ({sys_info.get('os_release')})",
            f"- **Platform String**: `{sys_info.get('os_version')}`",
            f"- **Architecture / Machine**: {sys_info.get('machine')} / {sys_info.get('processor')}",
            f"- **Python Version**: {sys_info.get('python_version')}",
            f"- **PySide6 / Qt**: {sys_info.get('pyside_version', 'N/A')} (Qt {sys_info.get('qt_version', 'N/A')})",
            "",
            "## 2. Storage & Filesystem",
            f"- **User Data Directory**: `{paths.get('user_data_dir')}` (Exists: {paths.get('user_data_exists')})",
            f"- **Database Path**: `{paths.get('db_path')}` (Exists: {paths.get('db_exists')}, Size: {paths.get('db_size_kb', 0)} KB)",
            f"- **Crash Dumps Directory**: `{paths.get('crash_dumps_dir')}` (Dumps found: {paths.get('crash_dump_count', 0)})",
            "",
            "## 3. Database & Schema Status",
            f"- **Connection Status**: {db_info.get('connection_status')}",
            f"- **SQLite WAL Mode**: {db_info.get('journal_mode', 'N/A')}",
            f"- **Foreign Keys Enabled**: {db_info.get('foreign_keys', 'N/A')}",
            "### Table Counts:",
        ]

        table_counts = db_info.get("table_counts", {})
        if table_counts:
            for tbl, count in sorted(table_counts.items()):
                md_lines.append(f"  - **{tbl}**: {count}")
        else:
            md_lines.append("  - *(No table stats available or DB unreachable)*")

        md_lines.extend([
            "",
            "## 4. AI Provider Configuration",
            f"- **Configured Provider**: `{ai_info.get('active_provider', 'none')}`",
            f"- **Active Model**: `{ai_info.get('active_model', 'none')}`",
            f"- **API Key Configured**: {ai_info.get('has_api_key', False)}",
            f"- **Base Endpoint**: `{ai_info.get('endpoint', 'default')}`",
            "",
            "## 5. Platform Readiness & Accounts",
        ])

        if isinstance(platforms, dict) and platforms and "error" not in platforms:
            for p_name, p_state in sorted(platforms.items()):
                if isinstance(p_state, dict):
                    md_lines.append(f"### {p_name.capitalize()}")
                    md_lines.append(f"- **Enabled**: {p_state.get('enabled', False)}")
                    md_lines.append(f"- **Has Credentials**: {p_state.get('has_credentials', False)}")
                    md_lines.append(f"- **Search Freshness**: {p_state.get('search_freshness', 'N/A')}")
                    md_lines.append(f"- **Automation Ready**: {p_state.get('automation_ready', False)}")
                else:
                    md_lines.append(f"- **{p_name}**: {p_state}")
        elif isinstance(platforms, dict) and "error" in platforms:
            md_lines.append(f"- *(Error reading platforms: {platforms['error']})*")
        else:
            md_lines.append("- *(No platforms configured)*")

        md_lines.extend([
            "",
            "## 6. Workspace Readiness Diagnostics",
            f"- **Core Workspace Ready**: {readiness.get('is_core_ready', False)} ({readiness.get('core_summary', '')})",
            f"- **Automation Ready**: {readiness.get('is_automation_ready', False)} ({readiness.get('recommended_summary', '')})",
        ])

        blockers = readiness.get("blockers", [])
        if blockers:
            md_lines.append("### Active Blockers:")
            for b in blockers:
                md_lines.append(f"- ⚠️ {b}")

        warnings = readiness.get("warnings", [])
        if warnings:
            md_lines.append("### Recommendations / Warnings:")
            for w in warnings:
                md_lines.append(f"- ℹ️ {w}")

        md_lines.extend([
            "",
            "## 7. Recent Diagnostic Logs (Sanitized)",
            "```text",
        ])

        if logs:
            for log_line in logs:
                md_lines.append(log_line)
        else:
            md_lines.append("No recent warning or error logs recorded.")

        md_lines.extend([
            "```",
            "",
            "---",
            "*Report is automatically scrubbed by JobPilot LogSanitizer. No plain passwords, tokens, or cookies are present.*",
        ])

        return "\n".join(md_lines)

    def export_to_file(self, destination_path: Optional[Path | str] = None) -> Path:
        """Exports sanitized markdown diagnostic report to a designated file path."""
        if not destination_path:
            now_str = datetime.now().strftime("%Y%m%d_%H%M%S")
            dest = Path.cwd() / "logs" / f"jobpilot_diagnostic_report_{now_str}.md"
        else:
            dest = Path(destination_path)

        dest.parent.mkdir(parents=True, exist_ok=True)
        content = self.generate_markdown()
        dest.write_text(content, encoding="utf-8")
        logger.info(f"Exported sanitized diagnostic report to {dest}")
        return dest

    # Internal Collectors

    def _collect_system_info(self) -> Dict[str, Any]:
        info: Dict[str, Any] = {
            "os": platform.system(),
            "os_release": platform.release(),
            "os_version": platform.version(),
            "machine": platform.machine(),
            "processor": platform.processor(),
            "python_version": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
        }
        try:
            import PySide6.QtCore
            info["pyside_version"] = PySide6.__version__
            info["qt_version"] = PySide6.QtCore.__version__
        except Exception:
            info["pyside_version"] = "unavailable"
            info["qt_version"] = "unavailable"
        return info

    def _collect_storage_paths(self) -> Dict[str, Any]:
        user_data = AppPaths.get_user_data_dir()
        db_cfg = DatabaseConfig()
        db_path = db_cfg.db_path

        dumps_dir = AppPaths.get_crash_dumps_dir(project_root=Path.cwd())
        dump_count = len(list(dumps_dir.glob("*.json"))) if dumps_dir.exists() else 0

        db_size_kb = 0
        if db_path.exists() and db_path.is_file():
            try:
                db_size_kb = round(db_path.stat().st_size / 1024, 1)
            except Exception:
                pass

        return {
            "user_data_dir": str(user_data),
            "user_data_exists": user_data.exists(),
            "db_path": str(db_path),
            "db_exists": db_path.exists(),
            "db_size_kb": db_size_kb,
            "crash_dumps_dir": str(dumps_dir),
            "crash_dump_count": dump_count,
        }

    def _collect_database_stats(self) -> Dict[str, Any]:
        stats: Dict[str, Any] = {
            "connection_status": "disconnected",
            "journal_mode": "unknown",
            "foreign_keys": "unknown",
            "table_counts": {},
        }
        try:
            from sqlalchemy import text
            with get_db_session(self._session_factory) as session:
                conn = session.connection()
                jm = conn.execute(text("PRAGMA journal_mode;")).scalar()
                fk = conn.execute(text("PRAGMA foreign_keys;")).scalar()
                stats["journal_mode"] = str(jm)
                stats["foreign_keys"] = bool(fk)
                stats["connection_status"] = "connected"

                # Table row counts
                tables = [
                    "jobs", "job_opportunities", "applications", "resumes",
                    "profiles", "professional_profiles", "qna_entries",
                    "platform_accounts", "communications", "interviews",
                    "follow_ups", "job_deduplication_evidence"
                ]
                existing_tables = [
                    r[0] for r in conn.execute(text("SELECT name FROM sqlite_master WHERE type='table';")).fetchall()
                ]

                counts = {}
                for t in tables:
                    if t in existing_tables:
                        try:
                            cnt = conn.execute(text(f"SELECT COUNT(*) FROM {t};")).scalar()
                            counts[t] = cnt
                        except Exception:
                            counts[t] = "error"
                stats["table_counts"] = counts
        except Exception as e:
            stats["connection_status"] = f"error: {str(e)}"
        return stats

    def _collect_ai_config(self) -> Dict[str, Any]:
        ai_cfg: Dict[str, Any] = {
            "active_provider": "unknown",
            "active_model": "unknown",
            "has_api_key": False,
            "endpoint": "default",
        }
        try:
            from app.services.ai_service import UniversalAIService
            service = UniversalAIService()
            cfg = service.get_config() or {}
            provider = cfg.get("provider", "unknown")
            ai_cfg["active_provider"] = provider
            ai_cfg["active_model"] = cfg.get("model", "unknown")
            ai_key = cfg.get("api_key", "")
            ai_cfg["has_api_key"] = bool(ai_key and len(str(ai_key).strip()) > 0)
            endpoint = cfg.get("api_url", "")
            if endpoint:
                ai_cfg["endpoint"] = LogSanitizer.sanitize_text(endpoint)
        except Exception as e:
            ai_cfg["error"] = f"could not load ai config: {str(e)}"
        return ai_cfg

    def _collect_platform_states(self) -> Dict[str, Any]:
        platform_data: Dict[str, Any] = {}
        try:
            from app.services.platform_service import PlatformService
            p_svc = PlatformService(self._session_factory)
            platforms = p_svc.list_platforms()
            for p in platforms:
                s_cfg = p_svc.get_search_config(p.name) or {}
                freshness = s_cfg.get("search_freshness", s_cfg.get("freshness_days", s_cfg.get("date_posted", "default")))
                p_cfg = p_svc.get_platform_config(p.name) or {}
                has_creds = bool(p_cfg.get("username") or p_cfg.get("email") or p_cfg.get("has_session"))
                platform_data[p.name] = {
                    "enabled": bool(p.is_enabled),
                    "has_credentials": has_creds,
                    "search_freshness": freshness,
                    "automation_ready": bool(p.is_enabled),
                }
        except Exception as e:
            platform_data["error"] = str(e)
        return platform_data

    def _collect_readiness_summary(self) -> Dict[str, Any]:
        try:
            from app.services.setup.setup_readiness import SetupReadinessService
            r_svc = SetupReadinessService()
            eval_res = r_svc.evaluate()
            return {
                "is_core_ready": eval_res.is_core_ready,
                "is_automation_ready": eval_res.is_automation_ready,
                "core_summary": eval_res.core_summary,
                "recommended_summary": eval_res.recommended_summary,
                "blockers": eval_res.blockers,
                "warnings": eval_res.warnings,
            }
        except Exception as e:
            return {"error": f"readiness evaluation failed: {str(e)}"}

    def _collect_recent_logs(self, max_lines: int = 35) -> List[str]:
        """Tails the last error and warning lines from logs/log.txt."""
        log_file = Path.cwd() / "logs" / "log.txt"
        if not log_file.exists():
            return []

        try:
            lines = log_file.read_text(encoding="utf-8", errors="replace").splitlines()
            # Filter for WARNING, ERROR, CRITICAL or last lines
            flagged = [
                l for l in lines
                if any(level in l for level in ("ERROR", "WARNING", "CRITICAL", "Traceback", "Exception"))
            ]
            tail = flagged[-max_lines:] if flagged else lines[-max_lines:]
            return [LogSanitizer.sanitize_text(line) for line in tail]
        except Exception as e:
            return [f"Could not read logs: {str(e)}"]
