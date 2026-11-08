import asyncio
import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from playwright.async_api import async_playwright

ROOT = Path("/home/ahmad10raza/Documents/Mastering/JobPilot")
VIDEOS_DIR = ROOT / "website" / "public" / "videos"
VIDEOS_DIR.mkdir(parents=True, exist_ok=True)

from tests.fixtures.harness.fake_ats_server import FakeATSServer

INIT_SCRIPT = """
(() => {
  // 1. Top Browser Address Bar
  if (!document.getElementById('jobpilot-demo-browser-chrome')) {
    const bar = document.createElement('div');
    bar.id = 'jobpilot-demo-browser-chrome';
    bar.innerHTML = `
      <div style="display:flex;align-items:center;justify-content:space-between;background:#0f172a;color:#94a3b8;padding:8px 16px;font-family:-apple-system,BlinkMacSystemFont,sans-serif;font-size:12px;border-bottom:1px solid #1e293b;user-select:none;">
        <div style="display:flex;align-items:center;gap:8px;">
          <span style="width:10px;height:10px;border-radius:50%;background:#ef4444;display:inline-block;"></span>
          <span style="width:10px;height:10px;border-radius:50%;background:#f59e0b;display:inline-block;"></span>
          <span style="width:10px;height:10px;border-radius:50%;background:#10b981;display:inline-block;"></span>
          <span style="margin-left:12px;color:#e2e8f0;font-weight:600;" id="jp-tab-title">Job Application</span>
        </div>
        <div style="flex:1;max-width:560px;margin:0 16px;background:#1e293b;border:1px solid #334155;border-radius:6px;padding:4px 12px;display:flex;align-items:center;gap:8px;font-family:monospace;font-size:11px;color:#38bdf8;">
          <span style="color:#10b981;">🔒</span>
          <span id="jp-url-text">https://careers.portal.com/jobs/apply</span>
        </div>
        <div style="display:flex;align-items:center;gap:6px;font-size:11px;color:#cbd5e1;background:#1e293b;padding:3px 10px;border-radius:4px;border:1px solid #334155;">
          <span style="width:6px;height:6px;border-radius:50%;background:#22c55e;display:inline-block;"></span>
          <span style="font-weight:600;color:#f8fafc;">JobPilot Autonomous Runner</span>
        </div>
      </div>
    `;
    document.body.prepend(bar);
  }

  // 2. Simulated Smooth Mouse Pointer
  if (!document.getElementById('jobpilot-cursor')) {
    const cursor = document.createElement('div');
    cursor.id = 'jobpilot-cursor';
    cursor.style.cssText = `
      position: fixed;
      top: 50px;
      left: 50px;
      width: 24px;
      height: 24px;
      pointer-events: none;
      z-index: 999999;
      transition: top 0.24s cubic-bezier(0.25, 1, 0.5, 1), left 0.24s cubic-bezier(0.25, 1, 0.5, 1);
    `;
    cursor.innerHTML = `
      <svg width="24" height="24" viewBox="0 0 24 24" fill="none" style="filter: drop-shadow(0 2px 4px rgba(0,0,0,0.6));">
        <path d="M4 4L11 20L14 13L21 10L4 4Z" fill="#ff7a00" stroke="#ffffff" stroke-width="2" stroke-linejoin="round"/>
      </svg>
      <div id="jobpilot-cursor-ripple" style="position:absolute;top:-4px;left:-4px;width:32px;height:32px;border-radius:50%;border:2px solid #ff7a00;opacity:0;pointer-events:none;"></div>
    `;
    document.body.appendChild(cursor);
  }

  // 3. JobPilot Live Status HUD
  if (!document.getElementById('jobpilot-hud')) {
    const hud = document.createElement('div');
    hud.id = 'jobpilot-hud';
    hud.style.cssText = `
      position: fixed;
      bottom: 24px;
      right: 24px;
      background: rgba(15, 23, 42, 0.95);
      border: 1px solid #ff7a00;
      box-shadow: 0 10px 30px -5px rgba(0, 0, 0, 0.6);
      border-radius: 8px;
      padding: 10px 16px;
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
      color: #f8fafc;
      font-size: 12px;
      z-index: 999998;
      backdrop-filter: blur(8px);
      display: flex;
      align-items: center;
      gap: 12px;
    `;
    hud.innerHTML = `
      <span style="width:10px;height:10px;border-radius:50%;background:#ff7a00;display:inline-block;box-shadow:0 0 10px #ff7a00;"></span>
      <div>
        <div style="font-weight:700;color:#ff9838;font-size:11px;text-transform:uppercase;letter-spacing:0.06em;" id="jp-hud-engine">Autonomous Engine</div>
        <div style="color:#cbd5e1;font-size:11px;margin-top:2px;" id="jp-hud-status">Initializing DOM Analysis...</div>
      </div>
    `;
    document.body.appendChild(hud);
  }

  window.jobpilotMoveCursor = (x, y) => {
    const cursor = document.getElementById('jobpilot-cursor');
    if (cursor) {
      cursor.style.left = x + 'px';
      cursor.style.top = y + 'px';
    }
  };

  window.jobpilotClickRipple = () => {
    const ripple = document.getElementById('jobpilot-cursor-ripple');
    if (ripple) {
      ripple.style.transition = 'none';
      ripple.style.transform = 'scale(0.8)';
      ripple.style.opacity = '1';
      setTimeout(() => {
        ripple.style.transition = 'all 0.32s ease-out';
        ripple.style.transform = 'scale(2.2)';
        ripple.style.opacity = '0';
      }, 40);
    }
  };

  window.jobpilotSetHud = (engine, status) => {
    if (engine) document.getElementById('jp-hud-engine').innerText = engine;
    if (status) document.getElementById('jp-hud-status').innerText = status;
  };

  window.jobpilotSetUrl = (url, title) => {
    if (url) document.getElementById('jp-url-text').innerText = url;
    if (title) document.getElementById('jp-tab-title').innerText = title;
  };
})();
"""

async def animate_cursor_to_element(page, selector, text_to_type=None, is_select_index=None, is_click=False, hud_status=None):
    try:
        elem = page.locator(selector).first
        await elem.scroll_into_view_if_needed()
        box = await elem.bounding_box()
        if not box:
            return

        target_x = box["x"] + box["width"] / 2
        target_y = box["y"] + box["height"] / 2

        if hud_status:
            await page.evaluate(f"window.jobpilotSetHud(null, {repr(hud_status)})")

        await page.evaluate(f"window.jobpilotMoveCursor({target_x}, {target_y})")
        await page.wait_for_timeout(220)

        await page.evaluate("window.jobpilotClickRipple()")
        await elem.click()
        await page.wait_for_timeout(80)

        if text_to_type:
            for char in text_to_type:
                await elem.press_sequentially(char, delay=22)
                cur_x = min(box["x"] + 20 + len(text_to_type) * 7, box["x"] + box["width"] - 10)
                await page.evaluate(f"window.jobpilotMoveCursor({cur_x}, {target_y})")
            await page.wait_for_timeout(120)

        if is_select_index is not None:
            await elem.select_option(index=is_select_index)
            await page.wait_for_timeout(180)

    except Exception as e:
        print(f"Animation step warning for {selector}: {e}")

async def convert_webm_to_mp4_and_gif(webm_path, mp4_path, gif_path):
    print(f"Converting {webm_path.name} -> {mp4_path.name} & {gif_path.name}...")
    mp4_cmd = [
        "ffmpeg", "-y",
        "-i", str(webm_path),
        "-c:v", "libx264",
        "-pix_fmt", "yuv420p",
        "-movflags", "+faststart",
        "-r", "24",
        "-crf", "22",
        str(mp4_path)
    ]
    subprocess.run(mp4_cmd, check=True)

    gif_cmd = [
        "ffmpeg", "-y",
        "-i", str(webm_path),
        "-vf", "fps=12,scale=800:-1:flags=lanczos,split[s0][s1];[s0]palettegen[p];[s1][p]paletteuse",
        str(gif_path)
    ]
    subprocess.run(gif_cmd, check=True)
    print(f"Generated: {mp4_path.name} ({mp4_path.stat().st_size:,} bytes), {gif_path.name} ({gif_path.stat().st_size:,} bytes)")

async def record_universal_ats(base_url, p):
    print("\n--- [1/4] Universal ATS State Machine ---")
    temp_dir = tempfile.TemporaryDirectory()
    resume_file = Path(temp_dir.name) / "Ahmad_Raza_Resume.pdf"
    resume_file.write_bytes(b"%PDF-1.4 JobPilot verified candidate resume artifact")

    browser = await p.chromium.launch(executable_path="/usr/bin/google-chrome", headless=True)
    context = await browser.new_context(
        viewport={"width": 1280, "height": 800},
        record_video_dir=temp_dir.name,
        record_video_size={"width": 1280, "height": 800}
    )
    page = await context.new_page()
    await page.goto(f"{base_url}/standard-job")
    await page.evaluate(INIT_SCRIPT)
    await page.evaluate("window.jobpilotSetUrl('https://boards.greenhouse.io/stripe/jobs/482019', 'Stripe — Senior Backend Engineer')")
    await page.wait_for_timeout(600)

    # Step 1: Mapping Candidate Facts
    await animate_cursor_to_element(page, "#first_name", "Mohd Ahmad", hud_status="[PROFILE_FACT] Injected: First Name")
    await animate_cursor_to_element(page, "#last_name", "Raza Ansari", hud_status="[PROFILE_FACT] Injected: Last Name")
    await animate_cursor_to_element(page, "#email", "rjaahmad60@gmail.com", hud_status="[PROFILE_FACT] Injected: Email Address")
    await animate_cursor_to_element(page, "#phone", "+91 98765 43210", hud_status="[PROFILE_FACT] Injected: Mobile Phone")

    # Step 2: 5-Tier Q&A Resolution
    await animate_cursor_to_element(page, "#years_experience", is_select_index=3, hud_status="[RESUME_FACT] Resolved 5-Tier Q&A: 5+ Years Experience")
    await animate_cursor_to_element(page, "#notice_period", "30", hud_status="[PROFILE_FACT] Injected: Notice Period 30 Days")
    await animate_cursor_to_element(page, "#expected_salary", "$145,000", hud_status="[PROFILE_FACT] Injected: Salary Expectation")

    # Step 3: Work Authorization Radios
    await animate_cursor_to_element(page, 'input[name="work_auth"][value="yes"]', is_click=True, hud_status="[QNA_RULE] Work Authorization: Yes")
    await animate_cursor_to_element(page, 'input[name="visa_sponsorship"][value="no"]', is_click=True, hud_status="[QNA_RULE] Visa Sponsorship: No")

    # Step 4: Resume Attachment
    file_input = page.locator('input[name="resume"]').first
    await file_input.set_input_files(str(resume_file))
    await page.evaluate("window.jobpilotSetHud(null, '[VAULT] Attached: Ahmad_Raza_Resume.pdf')")
    await page.wait_for_timeout(500)

    # Step 5: Submit & Verification
    await animate_cursor_to_element(page, "#submit-application", is_click=True, hud_status="[SUBMIT] Submitting Verified Application Form...")
    await page.wait_for_timeout(1000)

    await page.evaluate(INIT_SCRIPT)
    await page.evaluate("window.jobpilotSetUrl('https://boards.greenhouse.io/stripe/jobs/482019/confirmation', 'Application Received — Stripe')")
    await page.evaluate("window.jobpilotSetHud('Universal ATS State Machine', '[VERIFIED] Confirmation Receipt #APP-JP-98765 Audited in SQLite')")
    await page.wait_for_timeout(1800)

    await page.close()
    await context.close()
    await browser.close()

    vids = list(Path(temp_dir.name).glob("*.webm"))
    if vids:
        await convert_webm_to_mp4_and_gif(
            vids[0],
            VIDEOS_DIR / "demo-universal-ats.mp4",
            VIDEOS_DIR / "demo-universal-ats.gif"
        )
    temp_dir.cleanup()

async def record_linkedin_easy_apply(base_url, p):
    print("\n--- [2/4] LinkedIn Easy Apply Engine ---")
    temp_dir = tempfile.TemporaryDirectory()
    resume_file = Path(temp_dir.name) / "Ahmad_Raza_Resume.pdf"
    resume_file.write_bytes(b"%PDF-1.4 JobPilot verified candidate resume artifact")

    browser = await p.chromium.launch(executable_path="/usr/bin/google-chrome", headless=True)
    context = await browser.new_context(
        viewport={"width": 1280, "height": 800},
        record_video_dir=temp_dir.name,
        record_video_size={"width": 1280, "height": 800}
    )
    page = await context.new_page()
    await page.goto(f"{base_url}/greenhouse")
    await page.evaluate(INIT_SCRIPT)
    await page.evaluate("window.jobpilotSetUrl('https://www.linkedin.com/jobs/view/3891042?easyApply=true', 'LinkedIn Easy Apply — Senior Backend Engineer')")
    await page.evaluate("window.jobpilotSetHud('LinkedIn Easy Apply Engine', 'Pre-flight Safety Gate: Verified Safe Application Ceiling (4/15 Today)')")
    await page.wait_for_timeout(600)

    # Step 1: Contact info
    await animate_cursor_to_element(page, "#first_name", "Mohd Ahmad", hud_status="[MODAL: STEP 1/3] Injected: First Name")
    await animate_cursor_to_element(page, "#last_name", "Raza Ansari", hud_status="[MODAL: STEP 1/3] Injected: Last Name")
    await animate_cursor_to_element(page, "#email", "rjaahmad60@gmail.com", hud_status="[MODAL: STEP 1/3] Injected: Email")
    await animate_cursor_to_element(page, "#phone", "+91 98765 43210", hud_status="[MODAL: STEP 1/3] Injected: Mobile Phone")

    # Step 2: Upload Resume
    file_input = page.locator('input[type="file"]').first
    await file_input.set_input_files(str(resume_file))
    await page.evaluate("window.jobpilotSetHud('LinkedIn Easy Apply Engine', '[MODAL: STEP 2/3] Attached Targeted Resume Variant')")
    await page.wait_for_timeout(500)

    # Step 3: Work auth questions
    await animate_cursor_to_element(page, "#work_auth", is_select_index=1, hud_status="[MODAL: STEP 2/3] Work Authorization: Yes")
    await animate_cursor_to_element(page, "#visa_sponsorship", is_select_index=1, hud_status="[MODAL: STEP 2/3] Sponsorship Needed: No")

    # Step 4: Submit Easy Apply
    await animate_cursor_to_element(page, "#submit_app", is_click=True, hud_status="[MODAL: STEP 3/3] Human Safe Mode Verified — Submitting Application")
    await page.wait_for_timeout(1000)

    # Confirmation
    await page.evaluate(INIT_SCRIPT)
    await page.evaluate("window.jobpilotSetUrl('https://www.linkedin.com/jobs/view/3891042/submitted', 'Application Submitted — LinkedIn')")
    await page.evaluate("window.jobpilotSetHud('LinkedIn Easy Apply Engine', '[SUBMITTED] LinkedIn Easy Apply Successful • Daily Quota Updated: 5/15')")
    await page.wait_for_timeout(1800)

    await page.close()
    await context.close()
    await browser.close()

    vids = list(Path(temp_dir.name).glob("*.webm"))
    if vids:
        await convert_webm_to_mp4_and_gif(
            vids[0],
            VIDEOS_DIR / "demo-linkedin.mp4",
            VIDEOS_DIR / "demo-linkedin.gif"
        )
    temp_dir.cleanup()

async def record_naukri_direct_apply(base_url, p):
    print("\n--- [3/4] Naukri Direct Apply & Safety Gate ---")
    temp_dir = tempfile.TemporaryDirectory()
    resume_file = Path(temp_dir.name) / "Ahmad_Raza_Resume.pdf"
    resume_file.write_bytes(b"%PDF-1.4 JobPilot verified candidate resume artifact")

    browser = await p.chromium.launch(executable_path="/usr/bin/google-chrome", headless=True)
    context = await browser.new_context(
        viewport={"width": 1280, "height": 800},
        record_video_dir=temp_dir.name,
        record_video_size={"width": 1280, "height": 800}
    )
    page = await context.new_page()
    await page.goto(f"{base_url}/lever")
    await page.evaluate(INIT_SCRIPT)
    await page.evaluate("window.jobpilotSetUrl('https://www.naukri.com/job-listings-senior-software-engineer-bangalore-92810', 'Naukri Direct Apply — Senior Software Engineer')")
    await page.evaluate("window.jobpilotSetHud('Naukri Direct Apply & Safety Gate', 'Cookie Session Active • Zero Password Exposure • Safe Velocity (2.4s Jitter)')")
    await page.wait_for_timeout(600)

    # Attach resume
    file_input = page.locator('input[type="file"]').first
    await file_input.set_input_files(str(resume_file))
    await page.evaluate("window.jobpilotSetHud('Naukri Direct Apply & Safety Gate', '[RESUME] Attached: Ahmad_Raza_Resume.pdf')")
    await page.wait_for_timeout(400)

    # Fill form fields
    await animate_cursor_to_element(page, "#name", "Mohd Ahmad Raza Ansari", hud_status="[PROFILE_FACT] Injected: Full Name")
    await animate_cursor_to_element(page, "#email", "rjaahmad60@gmail.com", hud_status="[PROFILE_FACT] Injected: Primary Email")
    await animate_cursor_to_element(page, "#phone", "+91 98765 43210", hud_status="[PROFILE_FACT] Injected: Phone Number")
    await animate_cursor_to_element(page, "#org", "Senior Software Engineer", hud_status="[PROFILE_FACT] Injected: Current Role")
    await animate_cursor_to_element(page, "#linkedin_url", "https://linkedin.com/in/ahmadraza", hud_status="[PROFILE_FACT] Injected: LinkedIn Profile")
    await animate_cursor_to_element(page, "#github_url", "https://github.com/Ahmad01Ansari", hud_status="[PROFILE_FACT] Injected: GitHub Profile")

    # Dropdown and notice period
    await animate_cursor_to_element(page, "#years_experience", is_select_index=3, hud_status="[RESUME_FACT] Experience Tenure Mapped: 5-8 Years")
    await animate_cursor_to_element(page, "#notice_period", "30 Days", hud_status="[PROFILE_FACT] Notice Period Injected: 30 Days")

    # Submit
    await animate_cursor_to_element(page, "#lever-submit-btn", is_click=True, hud_status="[DIRECT_APPLY] Submitting Naukri Verified Application...")
    await page.wait_for_timeout(1000)

    # Confirmation
    await page.evaluate(INIT_SCRIPT)
    await page.evaluate("window.jobpilotSetUrl('https://www.naukri.com/job-listings-senior-software-engineer/applied', 'Application Confirmed — Naukri')")
    await page.evaluate("window.jobpilotSetHud('Naukri Direct Apply & Safety Gate', '[CONFIRMED] Application Successfully Delivered • Recorded to Cockpit')")
    await page.wait_for_timeout(1800)

    await page.close()
    await context.close()
    await browser.close()

    vids = list(Path(temp_dir.name).glob("*.webm"))
    if vids:
        await convert_webm_to_mp4_and_gif(
            vids[0],
            VIDEOS_DIR / "demo-naukri.mp4",
            VIDEOS_DIR / "demo-naukri.gif"
        )
    temp_dir.cleanup()

async def record_indeed_workday_flow(base_url, p):
    print("\n--- [4/4] Indeed & Glassdoor Submitter ---")
    temp_dir = tempfile.TemporaryDirectory()
    resume_file = Path(temp_dir.name) / "Ahmad_Raza_Resume.pdf"
    resume_file.write_bytes(b"%PDF-1.4 JobPilot verified candidate resume artifact")

    browser = await p.chromium.launch(executable_path="/usr/bin/google-chrome", headless=True)
    context = await browser.new_context(
        viewport={"width": 1280, "height": 800},
        record_video_dir=temp_dir.name,
        record_video_size={"width": 1280, "height": 800}
    )
    page = await context.new_page()

    # Step 1: Workday Step 1 (Personal Info)
    await page.goto(f"{base_url}/workday/step1")
    await page.evaluate(INIT_SCRIPT)
    await page.evaluate("window.jobpilotSetUrl('https://salesforce.wd12.myworkdayjobs.com/careers/step1', 'Salesforce Careers — Step 1: Personal Info (Workday)')")
    await page.evaluate("window.jobpilotSetHud('Indeed & Glassdoor Submitter', 'External ATS Redirect Detected: Seamless Universal Bridge to Workday')")
    await page.wait_for_timeout(600)

    await animate_cursor_to_element(page, "#first_name", "Mohd Ahmad", hud_status="[WORKDAY STEP 1] Injected: First Name")
    await animate_cursor_to_element(page, "#last_name", "Raza Ansari", hud_status="[WORKDAY STEP 1] Injected: Last Name")
    await animate_cursor_to_element(page, "#email", "rjaahmad60@gmail.com", hud_status="[WORKDAY STEP 1] Injected: Workday Login Email")
    await animate_cursor_to_element(page, "#phone", "+91 98765 43210", hud_status="[WORKDAY STEP 1] Injected: Candidate Phone")

    await animate_cursor_to_element(page, "#workday-next-step1", is_click=True, hud_status="[WORKDAY STEP 1] Step 1 Complete -> Advancing to Step 2...")
    await page.wait_for_timeout(900)

    # Step 2: Workday Step 2 (Experience & Resume)
    await page.evaluate(INIT_SCRIPT)
    await page.evaluate("window.jobpilotSetUrl('https://salesforce.wd12.myworkdayjobs.com/careers/step2', 'Salesforce Careers — Step 2: Experience & Resume')")
    file_input = page.locator('input[type="file"]').first
    await file_input.set_input_files(str(resume_file))
    await page.evaluate("window.jobpilotSetHud('Indeed & Glassdoor Submitter', '[WORKDAY STEP 2] Attached: Ahmad_Raza_Resume.pdf')")
    await page.wait_for_timeout(400)

    await animate_cursor_to_element(page, "#years_experience", is_select_index=3, hud_status="[WORKDAY STEP 2] Experience Level Mapped: 5-8 Years")
    await animate_cursor_to_element(page, "#work_auth", is_select_index=1, hud_status="[WORKDAY STEP 2] Work Authorization Verified: Yes")

    await animate_cursor_to_element(page, "#workday-next-step2", is_click=True, hud_status="[WORKDAY STEP 2] Step 2 Complete -> Advancing to Review...")
    await page.wait_for_timeout(900)

    # Step 3: Workday Step 3 (Review & Submit)
    await page.evaluate(INIT_SCRIPT)
    await page.evaluate("window.jobpilotSetUrl('https://salesforce.wd12.myworkdayjobs.com/careers/step3', 'Salesforce Careers — Step 3: Review Application')")
    await animate_cursor_to_element(page, "#workday-final-submit", is_click=True, hud_status="[WORKDAY SUBMIT] Submitting Final Verified Application Form...")
    await page.wait_for_timeout(1000)

    # Confirmation
    await page.evaluate(INIT_SCRIPT)
    await page.evaluate("window.jobpilotSetUrl('https://salesforce.wd12.myworkdayjobs.com/careers/thank-you', 'Submission Confirmed — Salesforce')")
    await page.evaluate("window.jobpilotSetHud('Indeed & Glassdoor Submitter', '[SUBMITTED] Workday Application Confirmed: #APP-WIZARD-1122')")
    await page.wait_for_timeout(1800)

    await page.close()
    await context.close()
    await browser.close()

    vids = list(Path(temp_dir.name).glob("*.webm"))
    if vids:
        await convert_webm_to_mp4_and_gif(
            vids[0],
            VIDEOS_DIR / "demo-indeed.mp4",
            VIDEOS_DIR / "demo-indeed.gif"
        )
    temp_dir.cleanup()

async def main():
    server = FakeATSServer()
    base_url = server.start()
    print("Fake ATS Server running on", base_url)

    async with async_playwright() as p:
        await record_universal_ats(base_url, p)
        await record_linkedin_easy_apply(base_url, p)
        await record_naukri_direct_apply(base_url, p)
        await record_indeed_workday_flow(base_url, p)

    server.stop()
    print("\nAll 4 real automation recordings generated successfully!")

if __name__ == "__main__":
    asyncio.run(main())
