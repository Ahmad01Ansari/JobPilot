"""
Glassdoor Popup & Overlay Manager
Detects, classifies, and safely dismisses transient modals and overlays on Glassdoor.
Categorizes popups into:
- BENIGN (Job alerts, promotional popups, cookie consent) -> Safely dismissed.
- AUTH (Login / Sign-in required) -> Triggers LOGIN_REQUIRED intervention.
- SECURITY (CAPTCHA / Cloudflare Turnstile) -> Triggers CAPTCHA intervention.
- UNKNOWN -> Pauses if blocking critical UI interactions.
"""

from __future__ import annotations
import logging
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass

logger = logging.getLogger(__name__)


class PopupCategory(Enum):
    BENIGN = "BENIGN"
    AUTH = "AUTH"
    SECURITY = "SECURITY"
    UNKNOWN = "UNKNOWN"


@dataclass
class PopupDetectionResult:
    detected: bool
    category: PopupCategory
    name: str
    action_taken: str
    element_found: bool = False


class GlassdoorPopupManager:
    """Manages proactive discovery and dismissal of intrusive Glassdoor modals."""

    @classmethod
    def dismiss_benign_overlays(cls, driver: Any) -> int:
        """Executes targeted, safe JavaScript unlinking and dismissal of benign overlays."""
        if not driver:
            return 0

        try:
            dismissed_count = driver.execute_script('''
                var count = 0;

                // 1. "Create job alert" modal & close button
                var alertCloses = document.querySelectorAll(
                    "[data-test='job-alert-modal-close'], button[aria-label='Cancel'], .modal_CloseButton__faPZA button"
                );
                for (var btn of alertCloses) {
                    if (btn.offsetWidth > 0 && btn.offsetHeight > 0) {
                        try { btn.click(); count++; } catch(e) {}
                    }
                }

                // 2. Scan dialogs with "Create job alert" text
                var dialogs = document.querySelectorAll("div[role='dialog'], div[class*='modal'], div[class*='Modal']");
                for (var d of dialogs) {
                    var txt = (d.innerText || '').toLowerCase();
                    if (txt.includes('create job alert') || txt.includes('save this alert')) {
                        var cb = d.querySelector("button[aria-label*='Close' i], button[aria-label*='Cancel' i], button[data-test*='close'], button.close");
                        if (cb) {
                            try { cb.click(); count++; } catch(e) {}
                        } else {
                            try { d.remove(); count++; } catch(e) {}
                        }
                    }
                }

                // 3. Remove orphaned backdrops
                var backdrops = document.querySelectorAll(".modal_ModalOverlay, .hiding-modal, .ModalBackdrop, div[class*='Overlay']");
                for (var bd of backdrops) {
                    // Only remove if no active login or captcha dialog is present
                    var hasAuth = document.querySelector("input#inlineUserEmail, input#inlineUserPassword, #challenge-stage");
                    if (!hasAuth && (bd.offsetWidth > 0 || bd.offsetHeight > 0)) {
                        try { bd.remove(); count++; } catch(e) {}
                    }
                }

                // 4. OneTrust Cookie consent banner
                var cookieBtn = document.querySelector("#onetrust-accept-btn-handler, button#onetrust-accept-btn-handler");
                if (cookieBtn && cookieBtn.offsetWidth > 0) {
                    try { cookieBtn.click(); count++; } catch(e) {}
                }

                return count;
            ''')
            return int(dismissed_count or 0)
        except Exception as e:
            logger.debug(f"[GlassdoorPopupManager] Error during overlay dismissal: {e}")
            return 0
