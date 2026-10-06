'''
Browser Anti-Bot Stealth Configuration
Injects Chrome DevTools Protocol (CDP) scripts to mask automation indicators:
- Removes navigator.webdriver
- Defines window.chrome runtime object
- Masks navigator.plugins and navigator.languages
- Overrides navigator.permissions query for notifications
'''

from typing import Any
from modules.helpers import print_lg

STEALTH_CDP_SCRIPT = """
(() => {
    // 1. Mask navigator.webdriver
    Object.defineProperty(navigator, 'webdriver', {
        get: () => undefined,
        configurable: true
    });

    // 2. Mock window.chrome runtime properties
    if (!window.chrome) {
        window.chrome = {};
    }
    if (!window.chrome.runtime) {
        window.chrome.runtime = {
            OnInstalledReason: { INSTALL: "install", UPDATE: "update", CHROME_UPDATE: "chrome_update", SHARED_MODULE_UPDATE: "shared_module_update" },
            OnRestartRequiredReason: { APP_UPDATE: "app_update", OS_UPDATE: "os_update", PERIODIC: "periodic" },
            PlatformArch: { ARM: "arm", ARM64: "arm64", MIPS: "mips", MIPS64: "mips64", X86_32: "x86-32", X86_64: "x86-64" },
            PlatformNaclArch: { ARM: "arm", MIPS: "mips", MIPS64: "mips64", X86_32: "x86-32", X86_64: "x86-64" },
            PlatformOs: { ANDROID: "android", CROS: "cros", LINUX: "linux", MAC: "mac", OPENBSD: "openbsd", WIN: "win" },
            RequestUpdateCheckStatus: { THROTTLED: "throttled", NO_UPDATE: "no_update", UPDATE_AVAILABLE: "update_available" }
        };
    }
    if (!window.chrome.app) {
        window.chrome.app = {
            isInstalled: false,
            InstallState: { DISABLED: "disabled", INSTALLED: "installed", NOT_INSTALLED: "not_installed" },
            RunningState: { CANNOT_RUN: "cannot_run", READY_TO_RUN: "ready_to_run", RUNNING: "running" }
        };
    }
    if (!window.chrome.csi) {
        window.chrome.csi = function() {};
    }
    if (!window.chrome.loadTimes) {
        window.chrome.loadTimes = function() {};
    }

    // 3. Mock navigator.languages and plugins
    try {
        Object.defineProperty(navigator, 'languages', {
            get: () => ['en-US', 'en'],
            configurable: true
        });
    } catch(e) {}

    try {
        if (!navigator.plugins || navigator.plugins.length === 0) {
            Object.defineProperty(navigator, 'plugins', {
                get: () => [
                    { name: 'Chrome PDF Plugin', filename: 'internal-pdf-viewer', description: 'Portable Document Format' },
                    { name: 'Chrome PDF Viewer', filename: 'mhjfbmdgcfjbbpaeojofohoefgiehjai', description: '' }
                ],
                configurable: true
            });
        }
    } catch(e) {}

    // 4. Notification permissions mock
    try {
        const originalQuery = window.navigator.permissions ? window.navigator.permissions.query : null;
        if (originalQuery) {
            window.navigator.permissions.query = (parameters) => (
                parameters.name === 'notifications' ?
                    Promise.resolve({ state: Notification.permission }) :
                    originalQuery(parameters)
            );
        }
    } catch(e) {}
})();
"""


def apply_stealth_to_driver(driver: Any) -> bool:
    """Applies CDP-level evasions to undetected Chrome driver session.
    Safe to call with mocked drivers in test environments without raising errors.
    """
    if not driver:
        return False

    success = False
    # Method 1: execute_cdp_cmd on Chrome WebDriver
    if hasattr(driver, "execute_cdp_cmd"):
        try:
            driver.execute_cdp_cmd(
                "Page.addScriptToEvaluateOnNewDocument",
                {"source": STEALTH_CDP_SCRIPT}
            )
            success = True
        except Exception:
            pass

    # Method 2: In-page execute_script fallback for initial document
    try:
        driver.execute_script(STEALTH_CDP_SCRIPT)
        success = True
    except Exception:
        pass

    return success
