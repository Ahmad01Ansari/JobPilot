import os, sys, time, subprocess, re
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from selenium.webdriver.common.by import By
import undetected_chromedriver as uc
from platforms.indeed.applier import IndeedApplier
from platforms.indeed.search import IndeedJobItem

PROFILE_DIR = os.path.expanduser("~/.jobpilot-indeed-profile")

def get_chrome_major():
    try:
        res = subprocess.run(["google-chrome", "--version"], capture_output=True, text=True)
        m = re.search(r"(\d+)\.\d+\.\d+\.\d+", res.stdout)
        if m:
            return int(m.group(1))
    except Exception:
        pass
    return None

chrome_major = get_chrome_major()
options = uc.ChromeOptions()
options.page_load_strategy = 'eager'
prefs = {
    "profile.default_content_setting_values.geolocation": 2,
    "profile.default_content_setting_values.notifications": 2,
    "profile.default_content_setting_values.popups": 1,
}
options.add_experimental_option("prefs", prefs)
options.add_argument("--deny-permission-prompts")
options.add_argument("--disable-geolocation")
options.add_argument("--disable-gpu")
options.add_argument("--no-sandbox")
options.add_argument("--disable-dev-shm-usage")
options.add_argument("--window-size=1600,1000")

driver = uc.Chrome(
    options=options,
    user_data_dir=PROFILE_DIR,
    headless=False,
    version_main=chrome_major
)
driver.set_page_load_timeout(30)

try:
    url = "https://in.indeed.com/viewjob?jk=3d71953477b139c5"
    driver.get(url)
    time.sleep(4)
    class BrowserWrapper:
        def __init__(self, drv):
            self.driver = drv
    
    bw = BrowserWrapper(driver)
    applier = IndeedApplier(browser=bw)
    job = IndeedJobItem(job_id="3d71953477b139c5", title="Robotic Process Automation Engineer", company="FUTURESOFTINDIA", job_url=url)
    details = applier.extract_job_details(job)
    print("EXTRACTED DETAILS:")
    print("Description len:", len(job.description))
    print("Description snippet:", repr(job.description[:300]) if job.description else "EMPTY")
    print("Salary:", job.salary, job.salary_min, job.salary_max)
    print("Experience:", job.experience_text, job.required_experience_min, job.required_experience_max)
    print("Work style:", job.work_style)
    
    dom_info = driver.execute_script("""
        return {
            title: document.title,
            url: window.location.href,
            bodySnippet: document.body ? document.body.innerText.slice(0, 500) : "NO BODY",
            allIds: Array.from(document.querySelectorAll('[id]')).map(e => e.id).filter(id => id.toLowerCase().includes('job') || id.toLowerCase().includes('desc')),
            allTestIds: Array.from(document.querySelectorAll('[data-testid]')).map(e => e.getAttribute('data-testid')),
        };
    """)
    print("DOM INFO:", dom_info)
finally:
    driver.quit()
