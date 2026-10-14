'''
Chrome Session Management
'''


from modules.helpers import get_default_temp_profile, make_directories
import os
import sys
import re
import subprocess
from config.settings import run_in_background, stealth_mode, disable_extensions, safe_mode, file_name, failed_file_name, logs_folder_path, generated_resume_path
from config.questions import default_resume_path
if stealth_mode:
    import undetected_chromedriver as uc
else: 
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
    # from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.support.ui import WebDriverWait
from modules.helpers import find_default_profile_directory, critical_error_log, print_lg
from modules.stealth import apply_stealth_to_driver
from selenium.common.exceptions import SessionNotCreatedException


def find_chrome_executable(allow_fallback_chromium: bool = True) -> Optional[str]:
    """Resolves absolute path to installed Google Chrome or Chromium executable across operating systems.
    
    If allow_fallback_chromium is True, falls back to Brave, Chromium, or Microsoft Edge
    (standard on Windows VMs and systems where Chrome has not yet been installed).
    """
    configured = os.environ.get("CHROME_PATH")
    if configured and os.path.isfile(configured):
        return configured

    if os.name == "nt":
        # 1. Primary: Google Chrome
        candidates = [
            os.path.join(os.environ.get("LOCALAPPDATA", ""), "Google", "Chrome", "Application", "chrome.exe"),
            os.path.join(os.environ.get("PROGRAMFILES", ""), "Google", "Chrome", "Application", "chrome.exe"),
            os.path.join(os.environ.get("PROGRAMFILES(X86)", ""), "Google", "Chrome", "Application", "chrome.exe"),
            r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        ]
        for cand in candidates:
            if cand and os.path.isfile(cand):
                return cand

        # Query Windows Registry for Chrome App Path
        try:
            import winreg
            for root_key in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
                try:
                    with winreg.OpenKey(root_key, r"Software\Microsoft\Windows\CurrentVersion\App Paths\chrome.exe") as key:
                        val, _ = winreg.QueryValueEx(key, "")
                        if val and os.path.isfile(val):
                            return val
                except OSError:
                    pass
        except (ImportError, Exception):
            pass

        import shutil
        cand_which = shutil.which("chrome.exe") or shutil.which("chrome")
        if cand_which and os.path.isfile(cand_which):
            return cand_which

        # 2. Secondary Fallback: Brave, Chromium, and Microsoft Edge (preinstalled on all Windows OS/VMs)
        if allow_fallback_chromium:
            alt_candidates = [
                # Microsoft Edge (standard default on every Windows 10/11 system)
                os.path.join(os.environ.get("PROGRAMFILES(X86)", r"C:\Program Files (x86)"), "Microsoft", "Edge", "Application", "msedge.exe"),
                os.path.join(os.environ.get("PROGRAMFILES", r"C:\Program Files"), "Microsoft", "Edge", "Application", "msedge.exe"),
                os.path.join(os.environ.get("LOCALAPPDATA", ""), "Microsoft", "Edge", "Application", "msedge.exe"),
                r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
                r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
                # Brave Browser
                os.path.join(os.environ.get("PROGRAMFILES", ""), "BraveSoftware", "Brave-Browser", "Application", "brave.exe"),
                os.path.join(os.environ.get("LOCALAPPDATA", ""), "BraveSoftware", "Brave-Browser", "Application", "brave.exe"),
                # Chromium
                os.path.join(os.environ.get("PROGRAMFILES", ""), "Chromium", "Application", "chrome.exe"),
                os.path.join(os.environ.get("LOCALAPPDATA", ""), "Chromium", "Application", "chrome.exe"),
            ]
            for cand in alt_candidates:
                if cand and os.path.isfile(cand):
                    return cand

            # Registry check for Edge and Brave
            try:
                import winreg
                for app_binary in ("msedge.exe", "brave.exe"):
                    for root_key in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
                        try:
                            with winreg.OpenKey(root_key, rf"Software\Microsoft\Windows\CurrentVersion\App Paths\{app_binary}") as key:
                                val, _ = winreg.QueryValueEx(key, "")
                                if val and os.path.isfile(val):
                                    return val
                        except OSError:
                            pass
            except Exception:
                pass

            cand_alt_which = (
                shutil.which("msedge.exe")
                or shutil.which("msedge")
                or shutil.which("brave.exe")
                or shutil.which("brave")
            )
            if cand_alt_which and os.path.isfile(cand_alt_which):
                return cand_alt_which

    elif sys.platform == "darwin":
        mac_candidates = [
            "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
            "/Applications/Google Chrome Canary.app/Contents/MacOS/Google Chrome Canary",
            "/Applications/Chromium.app/Contents/MacOS/Chromium",
            "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser",
            "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
        ]
        for cand in mac_candidates:
            if os.path.isfile(cand):
                return cand
    else:
        # Linux / Unix
        import shutil
        binaries = ["google-chrome-stable", "google-chrome", "chromium-browser", "chromium"]
        if allow_fallback_chromium:
            binaries.extend(["brave-browser", "microsoft-edge-stable", "microsoft-edge"])
        for binary in binaries:
            found = shutil.which(binary)
            if found and os.path.isfile(found):
                return found

    return None


def get_installed_chrome_major_version() -> int | None:
    """Detects installed Google Chrome major version."""
    chrome_path = find_chrome_executable()
    if chrome_path:
        try:
            completed = subprocess.run([chrome_path, "--version"], capture_output=True, text=True, timeout=5)
            output = (completed.stdout or completed.stderr or "").strip()
            match = re.search(r"(\d+)\.\d+\.\d+\.\d+", output)
            if match:
                return int(match.group(1))
        except Exception:
            pass

    # Fallback to registry query on Windows
    if os.name == "nt":
        for reg_cmd in (
            ["reg", "query", r"HKEY_CURRENT_USER\Software\Google\Chrome\BLBeacon", "/v", "version"],
            ["reg", "query", r"HKEY_LOCAL_MACHINE\Software\Google\Chrome\BLBeacon", "/v", "version"],
        ):
            try:
                completed = subprocess.run(reg_cmd, capture_output=True, text=True, timeout=5)
                output = (completed.stdout or completed.stderr or "").strip()
                match = re.search(r"(\d+)\.\d+\.\d+\.\d+", output)
                if match:
                    return int(match.group(1))
            except Exception:
                pass

    return None


def create_undetected_chrome(options, profile_dir=None):
    chrome_path = find_chrome_executable()
    chrome_major = get_installed_chrome_major_version()

    kwargs = {"options": options, "user_data_dir": profile_dir}
    if chrome_path:
        kwargs["browser_executable_path"] = chrome_path
    if chrome_major:
        kwargs["version_main"] = chrome_major
        print_lg(
            f"Detected Chrome {chrome_major} at {chrome_path or 'default path'}. Using matching ChromeDriver."
        )
    else:
        print_lg(
            "Could not detect Chrome version automatically. Falling back to default detection."
        )

    return uc.Chrome(**kwargs)

def createChromeSession(isRetry: bool = False):
    make_directories([file_name,failed_file_name,logs_folder_path+"/screenshots",default_resume_path,generated_resume_path+"/temp"])
    # Set up WebDriver with Chrome Profile
    options = uc.ChromeOptions() if stealth_mode else Options()
    options.page_load_strategy = 'eager'
    prefs = {
        "profile.default_content_setting_values.geolocation": 2,
        "profile.default_content_setting_values.notifications": 2,
        "credentials_enable_service": False,
        "profile.password_manager_enabled": False,
    }
    options.add_experimental_option("prefs", prefs)
    options.add_argument("--start-maximized")
    options.add_argument("--deny-permission-prompts")
    options.add_argument("--disable-geolocation")
    if run_in_background:   options.add_argument("--headless")
    if disable_extensions:  options.add_argument("--disable-extensions")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")

    print_lg("IF YOU HAVE MORE THAN 10 TABS OPENED, PLEASE CLOSE OR BOOKMARK THEM! Or it's highly likely that application will just open browser and not do anything!")
    from modules.browser_lock import get_profile_dir, cleanup_stale_profile_locks

    if isRetry:
        print_lg("Will login with a guest profile, browsing history will not be saved in the browser!")
        profile_dir = get_default_temp_profile()
    elif safe_mode:
        print_lg("Safe mode enabled: using dedicated temp profile!")
        profile_dir = get_default_temp_profile()
    else:
        profile_dir = get_profile_dir("linkedin")
        print_lg(f"Using persistent LinkedIn profile: {profile_dir}")

    cleanup_stale_profile_locks(profile_dir)

    if stealth_mode:
        print_lg("Downloading Chrome Driver... This may take some time. Undetected mode requires download every run!")
        try:
            driver = create_undetected_chrome(options, profile_dir=profile_dir)
        except Exception as e:
            print_lg(f"[open_chrome] Initial Chrome launch failed ({e}), attempting stale lock cleanup retry...")
            cleanup_stale_profile_locks(profile_dir)
            driver = create_undetected_chrome(options, profile_dir=profile_dir)
    else:
        options.add_argument(f"--user-data-dir={profile_dir}")
        driver = webdriver.Chrome(options=options)
    driver.maximize_window()
    try:
        driver.set_page_load_timeout(35)
    except Exception:
        pass
    wait = WebDriverWait(driver, 5)
    actions = ActionChains(driver)
    apply_stealth_to_driver(driver)
    return options, driver, actions, wait

def _should_skip_linkedin_chrome_init() -> bool:
    """Checks if the CLI is running exclusively for a non-LinkedIn platform (e.g. --platform naukri) or in test/check mode."""
    if any("unittest" in arg for arg in sys.argv) or any("pytest" in arg for arg in sys.argv):
        return True
    if "--check-config" in sys.argv:
        return True
    if "--platform" in sys.argv:
        try:
            idx = sys.argv.index("--platform")
            if idx + 1 < len(sys.argv) and sys.argv[idx + 1].strip().lower() in ["naukri", "indeed", "foundit", "glassdoor"]:
                return True
        except Exception:
            pass
    return False

options, driver, actions, wait = None, None, None, None

if not _should_skip_linkedin_chrome_init():
    try:
        options, driver, actions, wait = createChromeSession()
    except SessionNotCreatedException as e:
        critical_error_log("Failed to create Chrome Session, retrying with guest profile", e)
        options, driver, actions, wait = createChromeSession(True)
    except Exception as e:
        critical_error_log("Failed to initialize Chrome session", e)
        msg = f"Failed to start Google Chrome:\n\n{e}\n\nPlease verify Google Chrome is installed and close any existing Chrome processes."
        if isinstance(e, TimeoutError):
            msg = "Couldn't download Chrome-driver. Set stealth_mode = False in config!"
        print_lg(msg)
        from modules.helpers import show_modern_alert as alert
        alert(msg, "Error in opening chrome")
        try:
            if driver:
                driver.quit()
        except Exception:
            pass
        sys.exit(1)

if driver:
    try:
        import signal

        def _terminate_chrome_session(signum, frame):
            try:
                if driver:
                    driver.quit()
            except Exception:
                pass
            sys.exit(0)

        signal.signal(signal.SIGTERM, _terminate_chrome_session)
        signal.signal(signal.SIGINT, _terminate_chrome_session)
    except Exception:
        pass
