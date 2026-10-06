"""Concrete Stagehand v4 implementation of the BrowserAgent interface."""

import json
import logging
import os
from pathlib import Path
import re
import shutil
import tempfile
from typing import Any, Dict, List, Optional

import sys

from stagehand import Stagehand, local_browser
from stagehand.browser import StagehandBrowser
from stagehand.page import Page

from app.services.automation.universal_agent.browser_agent.base import BrowserAgent
from app.services.automation.universal_agent.browser_agent.session_manager import UniversalSessionManager

logger = logging.getLogger(__name__)


def _patch_stagehand_extension_resolution() -> None:
    """Ensures Stagehand unpacked extension directory is resolved accurately across frozen PyInstaller bundles and source trees."""
    try:
        import stagehand.extension_assets
        import stagehand.browser

        def safe_extension_directory() -> Path:
            # 1. Check default stagehand extension directory
            try:
                candidate = Path(stagehand.extension_assets.__file__).with_name("_extension")
                if (candidate / "manifest.json").is_file():
                    return candidate
            except Exception:
                pass

            # 2. Check PyInstaller _MEIPASS (frozen temporary bundle)
            if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
                meipass = Path(sys._MEIPASS)
                for d in [
                    meipass / "stagehand" / "_extension",
                    meipass / "_internal" / "stagehand" / "_extension",
                    meipass / "_extension",
                ]:
                    if (d / "manifest.json").is_file():
                        return d

            # 3. Check relative to executable (one-dir bundle, e.g. /opt/jobpilot/jobpilot)
            exe_dir = Path(sys.executable).parent
            for d in [
                exe_dir / "_internal" / "stagehand" / "_extension",
                exe_dir / "stagehand" / "_extension",
                exe_dir / "_extension",
            ]:
                if (d / "manifest.json").is_file():
                    return d

            # 4. Check virtual environment or site-packages fallback
            for prefix in [Path.home() / ".venv", Path.cwd() / ".venv", Path(sys.prefix)]:
                sp_cand = prefix / "lib" / f"python{sys.version_info.major}.{sys.version_info.minor}" / "site-packages" / "stagehand" / "_extension"
                if (sp_cand / "manifest.json").is_file():
                    return sp_cand

            # 5. Fallback
            return Path(stagehand.extension_assets.__file__).resolve().parents[3] / "extension" / "dist"

        stagehand.extension_assets.extension_directory = safe_extension_directory
        stagehand.browser.extension_directory = safe_extension_directory
    except Exception as e:
        logger.warning(f"Could not patch Stagehand extension resolver: {e}")


_patch_stagehand_extension_resolution()


class StagehandBrowserAgent(BrowserAgent):
    """Concrete browser automation agent powered by Stagehand v4 and Playwright."""

    def __init__(self, session_manager: Optional[UniversalSessionManager] = None) -> None:
        self.session_manager = session_manager or UniversalSessionManager()
        self.browser: Optional[StagehandBrowser] = None
        self.stagehand: Optional[Stagehand] = None
        self.page: Optional[Page] = None
        self._is_initialized: bool = False

    @property
    def is_initialized(self) -> bool:
        return self._is_initialized and self.page is not None

    async def initialize(self, headless: bool = False, model: Optional[Any] = None, **kwargs: Any) -> None:
        """Launches isolated Stagehand browser session."""
        if self.is_initialized:
            return

        launch_options = self.session_manager.get_launch_options(headless=headless, **kwargs)
        self.browser = await local_browser.launch(**launch_options)

        # Initialize Stagehand with native caching and self-healing
        self.stagehand = await Stagehand.create(
            browser=self.browser,
            model=model,
            dom_settle_timeout_ms=3000,
            cache=True,
            self_heal=True,
        )

        # Acquire primary active page
        pages = await self.browser.context.pages()
        if pages:
            self.page = pages[0]
        else:
            self.page = await self.browser.context.new_page()

        if not headless and self.page:
            try:
                await self.page.evaluate("() => { try { window.moveTo(0, 0); window.resizeTo(screen.availWidth, screen.availHeight); } catch(e){} }")
            except Exception:
                pass

        self._is_initialized = True

    async def sync_active_page(self, force_refresh: bool = False) -> None:
        """Synchronizes self.page to the most recently opened or focused page tab in the browser context."""
        if not self.browser or not self.browser.context:
            return
        try:
            # Stagehand RPC: calling context.pages refreshes the extension's internal page registry
            pages = await self.browser.context.pages()
            if not pages:
                try:
                    self.page = await self.browser.context.new_page()
                except Exception:
                    pass
                return

            current_page_ids = [p.page_id for p in pages if hasattr(p, "page_id")]

            # Check if self.page is missing or points to a closed/dead tab ID
            is_dead = (
                self.page is None
                or not hasattr(self.page, "page_id")
                or self.page.page_id not in current_page_ids
            )

            # Query context for active page
            active = None
            try:
                active = await self.browser.context.active_page()
            except Exception:
                active = None

            # Pick candidate target: if multiple tabs, prioritize destination company portals over job aggregators
            target_page = None
            if len(pages) > 1:
                aggregator_domains = ["naukri.com", "indeed.com", "linkedin.com", "foundit.in", "glassdoor.com"]
                portal_pages = []
                for p in pages:
                    try:
                        p_url = str(p.url).lower() if hasattr(p, "url") else ""
                        if p_url and not any(agg in p_url for agg in aggregator_domains) and not p_url.startswith("chrome://") and not p_url.startswith("about:"):
                            portal_pages.append(p)
                    except Exception:
                        pass

                if portal_pages:
                    target_page = portal_pages[-1]
                else:
                    target_page = pages[-1]
            elif active and hasattr(active, "page_id") and active.page_id in current_page_ids:
                target_page = active
            elif pages:
                target_page = pages[-1]

            if target_page:
                target_id = getattr(target_page, "page_id", None)
                current_id = getattr(self.page, "page_id", None)
                if is_dead or current_id != target_id or force_refresh:
                    logger.info("Switching active page to page_id=%s (tabs: %d, url=%s)", target_id, len(pages), getattr(target_page, 'url', ''))
                    self.page = target_page
                    try:
                        await self.browser.context.set_active_page(self.page)
                    except Exception:
                        pass
                    try:
                        await self.page.bring_to_front()
                    except Exception:
                        pass
        except Exception as e:
            logger.debug("sync_active_page error: %s", e)

    async def _safe_page_op(self, op_func: Any, default_val: Any = None, op_name: str = "operation") -> Any:
        """Safely executes an async operation on self.page with automatic context.pages recovery."""
        await self.sync_active_page()
        if not self.page:
            return default_val
        try:
            return await op_func(self.page)
        except Exception as e:
            err_str = str(e)
            if any(k in err_str for k in ["was not found", "context.pages", "Target closed", "closed", "destroyed"]):
                logger.warning("Stagehand page error during %s (%s). Re-syncing context.pages and retrying...", op_name, e)
                await self.sync_active_page(force_refresh=True)
                if self.page:
                    try:
                        return await op_func(self.page)
                    except Exception as retry_err:
                        logger.warning("Retry after re-sync failed for %s: %s", op_name, retry_err)
                        return default_val
            else:
                logger.debug("Error during %s: %s", op_name, e)
            return default_val

    async def navigate(self, url: str, wait_until: str = "domcontentloaded", timeout_ms: int = 30000) -> bool:
        from app.services.security.url_validator import is_safe_url
        is_safe, reason = is_safe_url(url, allow_local_ai=False)
        if not is_safe:
            logger.error("Navigation blocked by security policy for URL '%s': %s", url, reason)
            return False

        async def _do_nav(p: Page) -> bool:
            await p.goto(url)
            await p.wait_for_load_state(state="domcontentloaded")
            return True

        res = await self._safe_page_op(_do_nav, default_val=False, op_name=f"navigate({url})")
        return bool(res)

    async def act(self, action: str) -> Any:
        if not self.stagehand:
            raise RuntimeError("Stagehand not initialized.")
        await self.sync_active_page()
        try:
            return await self.stagehand.act(action, page=self.page)
        except Exception as e:
            err_str = str(e)
            if any(k in err_str for k in ["was not found", "context.pages", "Target closed", "closed"]):
                logger.warning("Stagehand page error during act (%s). Re-syncing context.pages and retrying...", e)
                await self.sync_active_page(force_refresh=True)
                try:
                    return await self.stagehand.act(action, page=self.page)
                except Exception as retry_err:
                    logger.warning("Retry failed for act: %s", retry_err)
                    return None
            logger.warning("Act error: %s", e)
            return None

    async def observe(self, instruction: str) -> List[Any]:
        if not self.stagehand:
            raise RuntimeError("Stagehand not initialized.")
        await self.sync_active_page()
        try:
            return await self.stagehand.observe(instruction, page=self.page)
        except Exception as e:
            err_str = str(e)
            if any(k in err_str for k in ["was not found", "context.pages", "Target closed", "closed"]):
                logger.warning("Stagehand page error during observe (%s). Re-syncing context.pages and retrying...", e)
                await self.sync_active_page(force_refresh=True)
                try:
                    return await self.stagehand.observe(instruction, page=self.page)
                except Exception as retry_err:
                    logger.warning("Retry failed for observe: %s", retry_err)
                    return []
            logger.warning("Observe error: %s", e)
            return []

    async def extract(self, instruction: str, schema: Any = None) -> Any:
        if not self.stagehand:
            raise RuntimeError("Stagehand not initialized.")
        await self.sync_active_page()
        try:
            if schema:
                return await self.stagehand.extract(instruction, schema=schema, page=self.page)
            return await self.stagehand.extract(instruction, page=self.page)
        except Exception as e:
            err_str = str(e)
            if any(k in err_str for k in ["was not found", "context.pages", "Target closed", "closed"]):
                logger.warning("Stagehand page error during extract (%s). Re-syncing context.pages and retrying...", e)
                await self.sync_active_page(force_refresh=True)
                try:
                    if schema:
                        return await self.stagehand.extract(instruction, schema=schema, page=self.page)
                    return await self.stagehand.extract(instruction, page=self.page)
                except Exception as retry_err:
                    logger.warning("Retry failed for extract: %s", retry_err)
                    return None
            logger.warning("Extract error: %s", e)
            return None

    async def fill(self, selector: str, value: str, timeout_ms: int = 5000) -> bool:
        async def _do_fill(p: Page) -> bool:
            locator = p.locator(selector)
            await locator.fill(value)
            return True

        res = await self._safe_page_op(_do_fill, default_val=False, op_name=f"fill({selector})")
        return bool(res)

    async def click(self, selector: str, timeout_ms: int = 5000) -> bool:
        async def _do_click(p: Page) -> bool:
            locator = p.locator(selector)
            await locator.click()
            return True

        res = await self._safe_page_op(_do_click, default_val=False, op_name=f"click({selector})")
        return bool(res)

    async def upload_file(self, selector: str, file_path: str, timeout_ms: int = 5000) -> bool:
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Upload file does not exist: {file_path}")

        async def _do_upload(p: Page) -> bool:
            locator = p.locator(selector)
            # Determine clean professional filename (strip internal hash prefix like res_2_5c1798bd_)
            base_name = os.path.basename(file_path)
            clean_name = re.sub(r"^res_[a-zA-Z0-9]+_[a-zA-Z0-9]+_", "", base_name)
            clean_name = re.sub(r"^res_[a-zA-Z0-9]+_", "", clean_name)
            if not clean_name.lower().endswith((".pdf", ".docx", ".doc")):
                clean_name = base_name

            upload_target = file_path
            if clean_name != base_name:
                try:
                    clean_dir = Path(tempfile.gettempdir()) / "jobpilot_clean_uploads"
                    clean_dir.mkdir(parents=True, exist_ok=True)
                    clean_file = clean_dir / clean_name
                    shutil.copy2(file_path, clean_file)
                    upload_target = str(clean_file)
                except Exception:
                    upload_target = file_path

            ext = os.path.splitext(clean_name)[1].lower()
            mime_map = {
                ".pdf": "application/pdf",
                ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                ".doc": "application/msword",
            }
            mime_type = mime_map.get(ext, "application/pdf")

            uploaded = False
            # 1. Primary: set_input_files with file path
            try:
                await locator.set_input_files(upload_target)
                uploaded = True
            except TypeError:
                try:
                    await locator.set_input_files(upload_target, timeout=timeout_ms)
                    uploaded = True
                except Exception:
                    pass
            except Exception:
                pass

            # 2. Secondary: set_input_files with Stagehand FilePayload
            if not uploaded:
                try:
                    from stagehand.file_upload import FilePayload
                    with open(file_path, "rb") as f:
                        file_buffer = f.read()
                    await locator.set_input_files(FilePayload(name=clean_name, buffer=file_buffer, mime_type=mime_type))
                    uploaded = True
                except Exception:
                    pass

            # 3. Fallback to first available file input on page
            if not uploaded:
                fallback_loc = p.locator('input[type="file"]').first
                try:
                    await fallback_loc.set_input_files(upload_target)
                    uploaded = True
                except Exception:
                    try:
                        from stagehand.file_upload import FilePayload
                        with open(file_path, "rb") as f:
                            file_buffer = f.read()
                        await fallback_loc.set_input_files(FilePayload(name=clean_name, buffer=file_buffer, mime_type=mime_type))
                        uploaded = True
                    except Exception:
                        pass

            if not uploaded:
                return False

            # Explicitly trigger React/ActiveStorage change and input events
            try:
                js_dispatch = f"""(() => {{
                    const el = document.querySelector({json.dumps(selector)}) || document.querySelector('input[type="file"]');
                    if (el) {{
                        el.dispatchEvent(new Event('input', {{ bubbles: true }}));
                        el.dispatchEvent(new Event('change', {{ bubbles: true }}));
                    }}
                }})()"""
                await p.evaluate(js_dispatch)
            except Exception:
                pass

            return True

        res = await self._safe_page_op(_do_upload, default_val=False, op_name=f"upload_file({selector})")
        return bool(res)

    async def select_option(self, selector: str, value: str, timeout_ms: int = 5000) -> bool:
        async def _do_select(p: Page) -> bool:
            locator = p.locator(selector)
            await locator.select_option(value)
            return True

        res = await self._safe_page_op(_do_select, default_val=False, op_name=f"select_option({selector})")
        return bool(res)

    async def get_url(self) -> str:
        res = await self._safe_page_op(lambda p: p.url(), default_val="", op_name="get_url")
        return str(res or "")

    async def get_title(self) -> str:
        res = await self._safe_page_op(lambda p: p.title(), default_val="", op_name="get_title")
        return str(res or "")

    async def get_content(self) -> str:
        res = await self._safe_page_op(
            lambda p: p.evaluate("document.documentElement.outerHTML"),
            default_val="",
            op_name="get_content",
        )
        return str(res or "")

    async def screenshot(self, path: Optional[str] = None) -> bytes:
        res = await self._safe_page_op(
            lambda p: p.screenshot(path=path),
            default_val=b"",
            op_name="screenshot",
        )
        return res if isinstance(res, bytes) else b""

    async def wait_for_selector(self, selector: str, timeout_ms: int = 5000) -> bool:
        res = await self._safe_page_op(
            lambda p: p.wait_for_selector(selector, timeout=float(timeout_ms) / 1000.0),
            default_val=False,
            op_name=f"wait_for_selector({selector})",
        )
        return bool(res)

    async def evaluate(self, expression: str) -> Any:
        return await self._safe_page_op(
            lambda p: p.evaluate(expression),
            default_val=None,
            op_name="evaluate",
        )

    async def close(self) -> None:
        """Closes the browser session, context, and handles cleanly."""
        if self.stagehand:
            try:
                await self.stagehand.close()
            except Exception:
                pass
            self.stagehand = None

        if self.browser:
            try:
                await self.browser.close()
            except Exception:
                pass
            self.browser = None

        self.page = None
        self._is_initialized = False
