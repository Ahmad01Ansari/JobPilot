# JobPilot — Browser Automation Rules
**Specialized Guidelines for Selenium, Undetected-Chromedriver, and Web Interaction**
*Reference: [Master Constitution](AI_DEVELOPMENT_RULES.md) §9*

---

## 1. Browser Automation Philosophy

Browser automation in JobPilot interfaces with complex, hostile, dynamically rendered single-page applications (SPAs) like LinkedIn, Naukri, Indeed, Glassdoor, and diverse ATS systems.

To ensure stability across thousands of applications, every browser interaction must follow the **OBSERVE → CLASSIFY → ACT → VERIFY** execution cycle.

```
┌────────────────────────────────────────────────────────┐
│                        OBSERVE                         │
│   Wait for DOM stability; inspect elements & context   │
└───────────────────────────┬────────────────────────────┘
                            │
┌───────────────────────────▼────────────────────────────┐
│                        CLASSIFY                        │
│   Identify widget type: input, radio, select, modal    │
└───────────────────────────┬────────────────────────────┘
                            │
┌───────────────────────────▼────────────────────────────┐
│                          ACT                           │
│   Scroll into view; interact with human-like timing    │
└───────────────────────────┬────────────────────────────┘
                            │
┌───────────────────────────▼────────────────────────────┐
│                         VERIFY                         │
│   Confirm DOM mutation; check value / step transition  │
└────────────────────────────────────────────────────────┘
```

---

## 2. Driver Management & Persistent Profiles

### 2.1. Dedicated Platform Profiles
Each platform maintains its own isolated Chrome user-data profile to prevent session cross-contamination:
- **LinkedIn:** `~/.jobpilot-chrome-profile` (fallback: `~/.apply-and-pray-chrome-profile`)
- **Naukri:** `~/.jobpilot-naukri-profile`
- **Indeed:** `~/.jobpilot-indeed-profile`
- **Glassdoor:** `~/.jobpilot-glassdoor-profile`
- **Universal ATS:** `~/.jobpilot-universal-profile`

### 2.2. Stale Lock Resolution
Chrome creates lock files (`SingletonLock`, `SingletonCookie`, `SingletonSocket`) on startup. If a previous run terminated abruptly, Chrome will crash on launch.
- **Rule:** Before launching any browser instance, always invoke `modules/browser_lock.py` to inspect and clean up stale locks.
- **Never** remove locks while an active browser PID is genuinely running.

### 2.3. Page Load Strategy & Timeouts
- Use `options.page_load_strategy = 'eager'`. SPAs often maintain active background WebSockets or analytics tracking that prevent the `'normal'` load strategy from ever firing.
- Always navigate using `safe_driver_get(driver, url, timeout)` to prevent hanging navigations.

---

## 3. The Search Window Preservation Invariant

When iterating through job search result lists:
1. **Never Navigate the Main Search Tab Away:**
   - Loading an application inside the primary search tab destroys pagination state, scroll offset, and search filters.
2. **Tab Lifecycle Standard:**
   ```
   Main Search Tab (Handle 0)
        │
        ├── Open Job in New Tab (Handle 1)
        ├── Switch to Handle 1
        ├── Extract Job Details & Requirements
        ├── Execute Application (Easy Apply / Smart Apply)
        ├── Close Tab (Handle 1)
        └── Switch Back to Main Search Tab (Handle 0)
   ```
3. **Emergency Recovery:**
   - If the main search tab is accidentally lost or closed, the engine must gracefully log the error, restore the search URL, and re-establish the search context rather than applying to random unrelated postings.

---

## 4. Resilient Element Interaction Guidelines

### 4.1. Explicit Waits Over Implicit Sleeps
- **Forbidden:** Blind `time.sleep(5)` statements.
- **Mandatory:** `WebDriverWait(driver, timeout).until(...)` checking element visibility, clickability, or presence.
- Minimal human jitter (`time.sleep(random.uniform(0.3, 0.8))`) is permitted only between user-like keystrokes.

### 4.2. Safe Click Pattern (Triple Fallback)
Single `.click()` calls frequently fail due to sticky navigation bars, floating banners, or intercepting overlays. Always use the triple fallback pattern:

```python
def safe_click(driver, element, timeout=5):
    """Click an element using human-like scroll, native click, and JS fallback."""
    try:
        # Step 1: Scroll into viewport center
        driver.execute_script(
            "arguments[0].scrollIntoView({block: 'center', inline: 'nearest'});",
            element
        )
        time.sleep(0.2)

        # Step 2: Attempt standard Selenium click
        element.click()
    except (ElementClickInterceptedException, ElementNotInteractableException):
        # Step 3: Fallback to direct JavaScript click
        driver.execute_script("arguments[0].click();", element)
```

### 4.3. Text Input & Keystroke Verification
- Clear existing text cleanly: `element.send_keys(Keys.CONTROL + "a", Keys.BACKSPACE)`.
- Send text with slight randomized delay if stealth mode is active.
- Verify value: Ensure `element.get_attribute("value")` matches the intended string.

---

## 5. Overlay, Dialog, & Popup Handling

Modern job platforms render unpredictable modals (e.g. "Save job alert?", "Rate your experience?", "Download our app?"):
1. **Dismiss Known Overlays:** Implement proactive dismissal handlers for known recurring modals.
2. **Backdrop Clicks:** If an unexpected overlay obscures the page, attempt pressing `Keys.ESCAPE` before failing.
3. **Iframes:** When forms render inside iframes (common in ATS portals), explicitly switch context (`driver.switch_to.frame(...)`) and always switch back (`driver.switch_to.default_content()`) upon completion.

---

## 6. CAPTCHA, Cloudflare, & Anti-Bot Boundaries

JobPilot strictly respects ethical and security boundaries:
1. **No CAPTCHA Bypass Hacks:**
   - Never implement automatic CAPTCHA solving, audio-recognition bypasses, or third-party paid solving APIs.
2. **Cooperative Pause (`PAUSED_FOR_INTERVENTION`):**
   - When a CAPTCHA, Cloudflare Turnstile challenge, or OTP wall is detected:
     - Pause automation immediately.
     - Emit `InterventionReason.CAPTCHA_DETECTED` via the bridge.
     - Alert the user via audio/visual prompt.
     - Wait for the user to solve it manually in the visible browser.
     - Verify page has cleared the challenge before resuming automated execution.
