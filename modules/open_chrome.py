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
from selenium.common.exceptions import SessionNotCreatedException


def get_installed_chrome_major_version() -> int | None:
    """Detects installed Google Chrome major version."""
    commands: list[list[str]] = []
    if os.name == "nt":
        commands.extend([[r"C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe", "--version"], [r"C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe", "--version"], ["reg", "query", r"HKEY_CURRENT_USER\\Software\\Google\\Chrome\\BLBeacon", "/v", "version"], ["reg", "query", r"HKEY_LOCAL_MACHINE\\Software\\Google\\Chrome\\BLBeacon", "/v", "version"]])
    elif sys.platform == "darwin":
        commands.append(["/Applications/Google Chrome.app/Contents/MacOS/Google Chrome", "--version"])
    else:
        commands.extend([["google-chrome", "--version"], ["google-chrome-stable", "--version"], ["chromium", "--version"], ["chromium-browser", "--version"]])
    for command in commands:
        try:
            completed = subprocess.run(command, capture_output=True, text=True, timeout=5)
            output = (completed.stdout or completed.stderr or "").strip()
            match = re.search(r"(\d+)\.\d+\.\d+\.\d+", output)
            if match: return int(match.group(1))
        except Exception:
            continue
    return None

def create_undetected_chrome(options):
    chrome_major = get_installed_chrome_major_version()

    if chrome_major:
        print_lg(
            f"Detected Chrome major version: {chrome_major}. Using matching ChromeDriver."
        )
        return uc.Chrome(options=options, version_main=chrome_major)

    print_lg(
        "Could not detect Chrome version automatically. Falling back to Chrome 149."
    )
    return uc.Chrome(options=options, version_main=149)
    print_lg("Could not detect Chrome version automatically. Falling back to default ChromeDriver detection.")
    return uc.Chrome(options=options)

def createChromeSession(isRetry: bool = False):
    make_directories([file_name,failed_file_name,logs_folder_path+"/screenshots",default_resume_path,generated_resume_path+"/temp"])
    # Set up WebDriver with Chrome Profile
    options = uc.ChromeOptions() if stealth_mode else Options()
    if run_in_background:   options.add_argument("--headless")
    if disable_extensions:  options.add_argument("--disable-extensions")

    print_lg("IF YOU HAVE MORE THAN 10 TABS OPENED, PLEASE CLOSE OR BOOKMARK THEM! Or it's highly likely that application will just open browser and not do anything!")
    profile_dir = find_default_profile_directory()
    if isRetry:
        print_lg("Will login with a guest profile, browsing history will not be saved in the browser!")
    elif profile_dir and not safe_mode:
        options.add_argument(f"--user-data-dir={profile_dir}")
    else:
        print_lg("Logging in with a guest profile, Web history will not be saved!")
        options.add_argument(f"--user-data-dir={get_default_temp_profile()}")
    if stealth_mode:
        # try: 
        #     driver = uc.Chrome(driver_executable_path="C:\\Program Files\\Google\\Chrome\\chromedriver-win64\\chromedriver.exe", options=options)
        # except (FileNotFoundError, PermissionError) as e: 
        #     print_lg("(Undetected Mode) Got '{}' when using pre-installed ChromeDriver.".format(type(e).__name__)) 
            print_lg("Downloading Chrome Driver... This may take some time. Undetected mode requires download every run!")
            driver = create_undetected_chrome(options)
    else: driver = webdriver.Chrome(options=options) #, service=Service(executable_path="C:\\Program Files\\Google\\Chrome\\chromedriver-win64\\chromedriver.exe"))
    driver.maximize_window()
    wait = WebDriverWait(driver, 5)
    actions = ActionChains(driver)
    return options, driver, actions, wait

try:
    options, driver, actions, wait = None, None, None, None
    options, driver, actions, wait = createChromeSession()
except SessionNotCreatedException as e:
    critical_error_log("Failed to create Chrome Session, retrying with guest profile", e)
    options, driver, actions, wait = createChromeSession(True)
except Exception as e:
    msg = 'Seems like Google Chrome is outdated. Update browser and try again! \n\nIf issue persists, try Safe Mode (set safe_mode = True in config/settings.py).'
    if isinstance(e,TimeoutError): msg = "Couldn't download Chrome-driver. Set stealth_mode = False in config!"
    print_lg(msg)
    critical_error_log("In Opening Chrome", e)
    from pyautogui import alert
    alert(msg, "Error in opening chrome")
    try: driver.quit()
    except NameError: exit()
    
