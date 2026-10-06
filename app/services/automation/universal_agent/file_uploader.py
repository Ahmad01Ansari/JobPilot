"""Native Playwright File Uploader for Universal Application Agent.

Handles resume document validation, SHA-256 verification, and headless file
attachment to <input type="file"> elements without operating system file dialog prompts.
"""

import hashlib
import os
from pathlib import Path
from typing import Optional, Tuple, Union

from app.services.automation.universal_agent.browser_agent.base import BrowserAgent

ALLOWED_EXTENSIONS = {".pdf", ".docx", ".doc"}
MAX_FILE_SIZE_BYTES = 15 * 1024 * 1024  # 15 MB


def calculate_sha256(file_path: str) -> str:
    """Computes SHA-256 hash of a local file."""
    sha = hashlib.sha256()
    with open(file_path, "rb") as f:
        while chunk := f.read(65536):
            sha.update(chunk)
    return sha.hexdigest()


class FileUploader:
    """Validates and executes file attachments using native browser automation."""

    def __init__(self, managed_storage_dir: Optional[Union[str, Path]] = None) -> None:
        if managed_storage_dir:
            self.managed_storage_dir = Path(managed_storage_dir).resolve()
        else:
            try:
                from app.services.os.app_paths import AppPaths
                self.managed_storage_dir = AppPaths.get_resumes_dir()
            except Exception:
                self.managed_storage_dir = Path.home() / ".jobpilot" / "managed_resumes"

    def validate_file(self, file_path: str, expected_hash: Optional[str] = None) -> Tuple[bool, Optional[str]]:
        """Verifies file existence, permissions, format, size, and optional integrity hash."""
        if not file_path:
            return False, "File path cannot be empty."

        path = Path(file_path).resolve()
        if not path.exists():
            return False, f"File does not exist: {file_path}"
        if not path.is_file():
            return False, f"Path is not a regular file: {file_path}"

        suffix = path.suffix.lower()
        if suffix not in ALLOWED_EXTENSIONS:
            return False, f"Unsupported file extension '{suffix}'. Allowed: {sorted(ALLOWED_EXTENSIONS)}"

        try:
            size = path.stat().st_size
            if size == 0:
                return False, "File is empty."
            if size > MAX_FILE_SIZE_BYTES:
                return False, f"File size ({size / (1024*1024):.1f}MB) exceeds limit of 15MB."
        except OSError as e:
            return False, f"Cannot read file metadata: {e}"

        if expected_hash:
            actual_hash = calculate_sha256(str(path))
            if actual_hash.lower() != expected_hash.lower():
                return False, f"SHA-256 integrity mismatch: expected {expected_hash}, got {actual_hash}"

        return True, None

    async def wait_for_upload_completion(
        self,
        agent: BrowserAgent,
        selector: str,
        max_wait_seconds: float = 12.0,
        poll_interval: float = 0.4,
    ) -> bool:
        """Polls dynamically until any direct upload / S3 transfer finishes and success signals appear."""
        import asyncio, json, time
        start_time = time.monotonic()
        sel_json = json.dumps(selector)

        js_check_completion = f"""(() => {{
            // 1. Check if progress bars / spinners are active
            const activeProgress = document.querySelector(
                '.file-field__progress:not([style*="width: 100%"]), [role="progressbar"], .upload-progress, .uploading, .spinner, .w-file-upload-uploading:not(.w-hidden)'
            );
            if (activeProgress && window.getComputedStyle(activeProgress).display !== 'none') {{
                const styleWidth = activeProgress.style.width || '';
                if (styleWidth && !styleWidth.startsWith('100%') && !styleWidth.startsWith('0%')) {{
                    return 'IN_PROGRESS';
                }}
                if (activeProgress.classList.contains('w-file-upload-uploading')) {{
                    return 'IN_PROGRESS';
                }}
            }}

            // 2. Check for Pinpoint ATS / Rails ActiveStorage direct upload tokens
            const hiddenUpload = document.querySelector(
                'input[type="hidden"][name*="[cv]"], input[type="hidden"][name*="[resume]"], input[type="hidden"][name*="[cover_letter]"], input[type="hidden"][name*="[attachment]"]'
            );
            if (hiddenUpload && hiddenUpload.value && hiddenUpload.value.length > 10) {{
                return 'COMPLETE';
            }}

            // 3. Check for tag removal buttons / success badges / Webflow upload success
            const successTag = document.querySelector(
                '.bp3-tag-remove, button[aria-label="Remove"], [aria-label*="Remove" i], [aria-label*="Delete" i], .bp3-intent-success, [class*="uploaded"], [class*="success-tag"], .file-field__filename, [class*="attached"], .w-file-upload-success:not(.w-hidden), .w-file-remove-link, .w-file-upload-file-name'
            );
            if (successTag && window.getComputedStyle(successTag).display !== 'none') {{
                return 'COMPLETE';
            }}

            // 4. Check native file input attachment
            const el = document.querySelector({sel_json}) || document.querySelector('input[type="file"][name*="cv"], input[type="file"][name*="resume"], input[type="file"]');
            if (el && el.type === "file" && el.files && el.files.length > 0) {{
                return 'ATTACHED';
            }}

            return 'WAITING';
        }})()"""

        while (time.monotonic() - start_time) < max_wait_seconds:
            try:
                eval_res = agent.evaluate(js_check_completion)
                res = await eval_res if asyncio.iscoroutine(eval_res) else eval_res
                state = str(res or "").upper()
                if state == "COMPLETE":
                    return True
                elif state == "ATTACHED":
                    # Allow extra settling time for DirectUpload network request to finish
                    await asyncio.sleep(1.5)
                    eval_res2 = agent.evaluate(js_check_completion)
                    res2 = await eval_res2 if asyncio.iscoroutine(eval_res2) else eval_res2
                    if str(res2 or "").upper() in ("COMPLETE", "ATTACHED"):
                        return True
            except Exception:
                pass
            await asyncio.sleep(poll_interval)

        # Timeout exhausted without positive completion signal — report failure
        logger.warning("Upload completion polling timed out after %.1fs for selector '%s'.", max_wait_seconds, selector)
        return False

    async def upload_file(
        self,
        agent: BrowserAgent,
        selector: str,
        file_path: str,
        expected_hash: Optional[str] = None,
        timeout_ms: int = 5000,
    ) -> Tuple[bool, Optional[str]]:
        """Attaches a local document to the file input target in the browser DOM."""
        # 1. Pre-upload file validation
        is_valid, err = self.validate_file(file_path, expected_hash=expected_hash)
        if not is_valid:
            return False, f"File validation failed: {err}"

        # 2. Execute upload via BrowserAgent
        resolved_path = str(Path(file_path).resolve())
        try:
            success = await agent.upload_file(selector, resolved_path, timeout_ms=timeout_ms)
            if not success:
                # Fallback to generic file input selector
                fallback_sel = 'input[type="file"][name*="cv"], input[type="file"][name*="resume"], input[type="file"]'
                try:
                    success = await agent.upload_file(fallback_sel, resolved_path, timeout_ms=timeout_ms)
                except Exception:
                    pass
            if not success:
                return False, f"Browser upload command failed on selector '{selector}'."
        except Exception as e:
            return False, f"Exception during file upload: {e}"

        # 3. Dynamic wait to confirm attachment and direct upload completion
        await self.wait_for_upload_completion(agent, selector, max_wait_seconds=12.0)

        # 4. Post-upload DOM attachment verification
        verified = await self.verify_upload(agent, selector)
        if not verified:
            # Check if direct upload replaced the input with a success tag or hidden signed ID
            js_has_tag = """(() => {
                const hidden = document.querySelector('input[type="hidden"][name*="[cv]"], input[type="hidden"][name*="[resume]"]');
                if (hidden && hidden.value) return true;
                const tag = document.querySelector('.bp3-tag-remove, button[aria-label="Remove"], [aria-label*="Remove" i], [aria-label*="Delete" i], .bp3-intent-success, .file-field__filename, .w-file-upload-success:not(.w-hidden), .w-file-remove-link, .w-file-upload-file-name');
                return !!tag;
            })()"""
            try:
                res = await agent.evaluate(js_has_tag)
                if res:
                    return True, None
            except Exception:
                pass
            return False, f"DOM verification failed: input '{selector}' has 0 attached files."

        return True, None

    async def verify_upload(self, agent: BrowserAgent, selector: str) -> bool:
        """Confirms that the target input[type='file'] has one or more files attached."""
        import json
        sel_json = json.dumps(selector)
        js_check = f"""(() => {{
            const el = document.querySelector({sel_json}) || document.querySelector('input[type="file"][name*="cv"], input[type="file"][name*="resume"], input[type="file"]');
            if (!el) {{
                const hidden = document.querySelector('input[type="hidden"][name*="[cv]"], input[type="hidden"][name*="[resume]"]');
                return hidden && hidden.value ? true : false;
            }}
            if (el.type !== "file") {{
                return !!el.value;
            }}
            if (el.files && el.files.length > 0) {{
                return true;
            }}
            const tag = document.querySelector('.bp3-tag-remove, button[aria-label="Remove"], [aria-label*="Remove" i], [aria-label*="Delete" i], .bp3-intent-success, .file-field__filename, .w-file-upload-success:not(.w-hidden), .w-file-remove-link, .w-file-upload-file-name');
            return !!tag;
        }})()"""
        try:
            res = await agent.evaluate(js_check)
            return bool(res)
        except Exception:
            return False
