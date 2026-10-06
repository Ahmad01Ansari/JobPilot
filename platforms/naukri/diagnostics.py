'''
Naukri Diagnostics & Failure Artifact Capture Module
Captures structured diagnostics on unknown UI states or questionnaire failures:
- logs/naukri_debug/job_<id>_<timestamp>/
  ├── screenshot.png
  ├── page_source.html
  ├── current_url.txt
  ├── question.txt
  ├── detected_inputs.json
  ├── detected_buttons.json
  └── error.txt
Strictly enforces credential and secret sanitization.
'''

import os
import json
import time
import re
from typing import Optional, Dict, Any, List
from modules.helpers import print_lg

DEBUG_DIR = "logs/naukri_debug"
SENSITIVE_PATTERNS = [
    re.compile(r"password", re.IGNORECASE),
    re.compile(r"secret", re.IGNORECASE),
    re.compile(r"token", re.IGNORECASE),
    re.compile(r"api[_-]?key", re.IGNORECASE),
    re.compile(r"cookie", re.IGNORECASE),
    re.compile(r"session", re.IGNORECASE),
]


def is_sensitive(key_or_val: str) -> bool:
    """Checks if a string represents sensitive credential data."""
    if not isinstance(key_or_val, str):
        return False
    return any(p.search(key_or_val) for p in SENSITIVE_PATTERNS)


def sanitize_text(text: str) -> str:
    """Masks potential passwords, API tokens, or secrets from logged text."""
    if not text:
        return ""
    # Redact common token and secret assignments
    sanitized = re.sub(
        r'(?i)(password|passwd|pwd|token|secret|apiKey)\s*[:=]\s*["\']?[^"\'\s,]+',
        r'\1: [REDACTED]',
        text
    )
    return sanitized


def capture_naukri_diagnostics(
    driver: Any,
    job_id: Optional[str] = None,
    context: str = "apply_failure",
    question: Optional[str] = None,
    error: Optional[str] = None,
    extra_info: Optional[Dict[str, Any]] = None,
) -> str:
    """
    Captures snapshot artifacts when questionnaire interaction or flow detection fails.
    Returns the folder path containing the captured diagnostics.
    """
    clean_job_id = re.sub(r'[^a-zA-Z0-9_\-]', '_', str(job_id or "unknown"))
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    folder_name = f"job_{clean_job_id}_{timestamp}"
    target_dir = os.path.join(DEBUG_DIR, folder_name)

    try:
        os.makedirs(target_dir, exist_ok=True)
    except Exception as e:
        print_lg(f"[NaukriDiagnostics] Could not create debug dir '{target_dir}': {e}")
        return ""

    # 1. Capture Screenshot
    try:
        if driver and hasattr(driver, "save_screenshot"):
            screenshot_path = os.path.join(target_dir, "screenshot.png")
            driver.save_screenshot(screenshot_path)
    except Exception as e:
        print_lg(f"[NaukriDiagnostics] Notice saving screenshot: {e}")

    # 2. Capture Page Source
    try:
        if driver and hasattr(driver, "page_source"):
            source = driver.page_source or ""
            source_path = os.path.join(target_dir, "page_source.html")
            with open(source_path, "w", encoding="utf-8") as f:
                f.write(sanitize_text(source))
    except Exception as e:
        print_lg(f"[NaukriDiagnostics] Notice saving page source: {e}")

    # 3. Capture Current URL
    try:
        curr_url = getattr(driver, "current_url", "") if driver else ""
        url_path = os.path.join(target_dir, "current_url.txt")
        with open(url_path, "w", encoding="utf-8") as f:
            f.write(curr_url or "URL unavailable")
    except Exception:
        pass

    # 4. Capture Question Prompt
    try:
        q_path = os.path.join(target_dir, "question.txt")
        with open(q_path, "w", encoding="utf-8") as f:
            f.write(sanitize_text(question or "No active question detected"))
    except Exception:
        pass

    # 5. Capture Detected Inputs
    detected_inputs: List[Dict[str, Any]] = []
    try:
        if driver and hasattr(driver, "find_elements"):
            from selenium.webdriver.common.by import By
            elements = driver.find_elements(
                By.XPATH,
                "//input | //textarea | //div[@contenteditable='true'] | //div[contains(@class, 'chip')] | //select"
            )
            for el in elements:
                try:
                    tag = (el.tag_name or "").lower()
                    inp_type = (el.get_attribute("type") or "").lower()
                    name = el.get_attribute("name") or ""
                    el_id = el.get_attribute("id") or ""
                    placeholder = el.get_attribute("placeholder") or ""
                    classes = el.get_attribute("class") or ""
                    is_disp = el.is_displayed()
                    is_enab = el.is_enabled()
                    val = el.get_attribute("value") or el.get_attribute("textContent") or ""

                    # Avoid logging sensitive fields
                    if is_sensitive(name) or is_sensitive(el_id) or inp_type == "password":
                        val = "[REDACTED]"

                    detected_inputs.append({
                        "tag": tag,
                        "type": inp_type,
                        "name": name,
                        "id": el_id,
                        "placeholder": placeholder,
                        "classes": classes,
                        "displayed": is_disp,
                        "enabled": is_enab,
                        "value_preview": str(val)[:50],
                    })
                except Exception:
                    continue
    except Exception:
        pass

    try:
        inp_path = os.path.join(target_dir, "detected_inputs.json")
        with open(inp_path, "w", encoding="utf-8") as f:
            json.dump(detected_inputs, f, indent=2)
    except Exception:
        pass

    # 6. Capture Detected Buttons
    detected_buttons: List[Dict[str, Any]] = []
    try:
        if driver and hasattr(driver, "find_elements"):
            from selenium.webdriver.common.by import By
            buttons = driver.find_elements(By.XPATH, "//button | //a[contains(@class, 'btn') or contains(@class, 'apply')]")
            for b in buttons:
                try:
                    text = (b.text or "").strip()
                    classes = b.get_attribute("class") or ""
                    is_disp = b.is_displayed()
                    is_enab = b.is_enabled()
                    btn_type = b.get_attribute("type") or ""
                    detected_buttons.append({
                        "text": text,
                        "type": btn_type,
                        "classes": classes,
                        "displayed": is_disp,
                        "enabled": is_enab,
                    })
                except Exception:
                    continue
    except Exception:
        pass

    try:
        btn_path = os.path.join(target_dir, "detected_buttons.json")
        with open(btn_path, "w", encoding="utf-8") as f:
            json.dump(detected_buttons, f, indent=2)
    except Exception:
        pass

    # 7. Capture Error Info
    try:
        err_path = os.path.join(target_dir, "error.txt")
        with open(err_path, "w", encoding="utf-8") as f:
            err_content = f"Context: {context}\n"
            if error:
                err_content += f"Error: {error}\n"
            if extra_info:
                err_content += f"Extra Info: {json.dumps(extra_info, default=str)}\n"
            f.write(sanitize_text(err_content))
    except Exception:
        pass

    print_lg(f"[NaukriDiagnostics] Captured diagnostic snapshot in '{target_dir}' for job '{clean_job_id}'.")
    return target_dir


def log_input_debug(
    question: str,
    detected_controls: List[str],
    selected_control: Optional[str],
    interaction: str,
    verification: str,
    reason: Optional[str] = None,
) -> None:
    """Logs structured terminal debugging information for questionnaire inputs (Section 17)."""
    print_lg("----------------------------------------------------------------------")
    print_lg("[NaukriInputDebug] Questionnaire Interaction Report:")
    print_lg(f"  Question          : {question}")
    print_lg(f"  Detected Controls : {', '.join(detected_controls) if detected_controls else 'None'}")
    print_lg(f"  Selected Control  : {selected_control or 'None'}")
    print_lg(f"  Interaction       : {interaction}")
    print_lg(f"  Verification      : {verification}")
    if reason:
        print_lg(f"  Reason            : {reason}")
    print_lg("----------------------------------------------------------------------")
