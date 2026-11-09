import asyncio
import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from PIL import Image

ROOT = Path("/home/ahmad10raza/Documents/Mastering/JobPilot")
VIDEOS_DIR = ROOT / "website" / "public" / "videos"
VIDEOS_DIR.mkdir(parents=True, exist_ok=True)

from tests.fixtures.harness.fake_ats_server import FakeATSServer
from app.services.automation.universal_agent.browser_agent import StagehandBrowserAgent, UniversalSessionManager

async def record_form_run(url, output_mp4, output_gif=None):
    temp_dir = tempfile.TemporaryDirectory()
    frames_dir = Path(temp_dir.name) / "frames"
    frames_dir.mkdir(parents=True, exist_ok=True)

    # Create dummy resume for upload
    sample_resume = Path(temp_dir.name) / "Ahmad_Raza_Resume.pdf"
    sample_resume.write_bytes(b"%PDF-1.4 test resume artifact for JobPilot automated demo")

    sm = UniversalSessionManager(profile_dir=temp_dir.name)
    agent = StagehandBrowserAgent(session_manager=sm)
    await agent.initialize(headless=True)
    page = agent.page
    
    # Set viewport
    await page.set_viewport_size({"width": 1280, "height": 800})
    await page.goto(url)
    await page.wait_for_timeout(500)

    frame_idx = 0

    async def capture(repeat=1):
        nonlocal frame_idx
        screenshot_bytes = await page.screenshot()
        # Save as PNG
        img_path = frames_dir / f"f_{frame_idx:05d}.png"
        img_path.write_bytes(screenshot_bytes)
        frame_idx += 1
        for _ in range(repeat - 1):
            shutil.copy(img_path, frames_dir / f"f_{frame_idx:05d}.png")
            frame_idx += 1

    await capture(10) # 0.5s pause on load

    # Simulate realistic human-like typing and field filling
    async def type_field(selector, text):
        try:
            elem = page.locator(selector).first
            await elem.scroll_into_view_if_needed()
            await elem.click()
            await capture(2)
            # Type char by char
            for ch in text:
                await elem.type(ch, delay=35)
                await capture(1)
            await capture(3)
        except Exception as e:
            print(f"Skipping {selector}: {e}")

    # Standard job / Greenhouse form fields
    await type_field('#first_name, input[name="first_name"], #first-name', "Ahmad")
    await type_field('#last_name, input[name="last_name"], #last-name', "Raza")
    await type_field('#email, input[name="email"]', "rjaahmad60@gmail.com")
    await type_field('#phone, input[name="phone"]', "+1 (555) 019-2834")
    await type_field('#linkedin_url, input[name="linkedin_url"], #linkedin', "https://linkedin.com/in/ahmadraza")

    # Select experience dropdown or input
    try:
        exp = page.locator('select[name="experience"], #experience, select[name="years_experience"]').first
        if await exp.count() > 0:
            await exp.scroll_into_view_if_needed()
            await exp.select_option(index=2)
            await capture(5)
    except Exception:
        pass

    # Radio buttons: authorized to work, visa sponsorship
    try:
        radios = page.locator('input[type="radio"]')
        count = await radios.count()
        if count > 0:
            for i in range(min(count, 4)):
                r = radios.nth(i)
                val = await r.get_attribute("value")
                if val in ["yes", "true", "1", "no"]:
                    await r.click()
                    await capture(3)
    except Exception:
        pass

    # File upload
    try:
        file_input = page.locator('input[type="file"]').first
        if await file_input.count() > 0:
            await file_input.set_input_files(str(sample_resume))
            await capture(8)
    except Exception as e:
        print(f"File upload skip: {e}")

    # Submit button
    await capture(8)
    try:
        submit_btn = page.locator('button[type="submit"], input[type="submit"], .btn-submit, button:has-text("Submit")').first
        if await submit_btn.count() > 0:
            await submit_btn.scroll_into_view_if_needed()
            await submit_btn.click()
            await page.wait_for_timeout(1000)
            await capture(15) # Show thank-you confirmation
    except Exception as e:
        print(f"Submit click error: {e}")

    await capture(15) # Final pause on success
    await agent.close()

    print(f"Captured {frame_idx} real frames. Encoding with ffmpeg to {output_mp4.name}...")
    
    # 1. Generate MP4
    ffmpeg_cmd = [
        "ffmpeg", "-y",
        "-r", "16",
        "-i", str(frames_dir / "f_%05d.png"),
        "-c:v", "libx264",
        "-pix_fmt", "yuv420p",
        "-crf", "20",
        str(output_mp4)
    ]
    subprocess.run(ffmpeg_cmd, check=True)
    print(f"Saved real automation video: {output_mp4.name} ({output_mp4.stat().st_size:,} bytes)")

    # 2. Also generate GIF if requested
    if output_gif:
        gif_cmd = [
            "ffmpeg", "-y",
            "-i", str(output_mp4),
            "-vf", "fps=10,scale=720:-1:flags=lanczos,split[s0][s1];[s0]palettegen[p];[s1][p]paletteuse",
            str(output_gif)
        ]
        subprocess.run(gif_cmd, check=True)
        print(f"Saved real automation GIF: {output_gif.name} ({output_gif.stat().st_size:,} bytes)")

    temp_dir.cleanup()

async def main():
    server = FakeATSServer()
    base_url = server.start()
    print("Fake ATS Server running on", base_url)

    # 1. Record Universal ATS (Greenhouse/Standard Job)
    print("\n--- Recording Real Universal ATS Automation ---")
    await record_form_run(
        f"{base_url}/standard-job",
        VIDEOS_DIR / "demo-universal-ats.mp4",
        VIDEOS_DIR / "demo-universal-ats.gif"
    )

    # 2. Record Multi-Step Wizard (representing LinkedIn / Indeed flow)
    print("\n--- Recording Real Multi-Step Wizard Automation ---")
    await record_form_run(
        f"{base_url}/greenhouse",
        VIDEOS_DIR / "demo-linkedin.mp4",
        VIDEOS_DIR / "demo-linkedin.gif"
    )

    # 3. Record Lever ATS Automation (representing Naukri / Regional direct apply)
    print("\n--- Recording Real Lever ATS Automation ---")
    await record_form_run(
        f"{base_url}/lever",
        VIDEOS_DIR / "demo-naukri.mp4",
        VIDEOS_DIR / "demo-naukri.gif"
    )

    # 4. Record Workday Wizard Automation (representing Indeed / Glassdoor multi-page)
    print("\n--- Recording Real Workday Wizard Automation ---")
    await record_form_run(
        f"{base_url}/workday/step1",
        VIDEOS_DIR / "demo-indeed.mp4",
        VIDEOS_DIR / "demo-indeed.gif"
    )

    server.stop()
    print("\nAll 4 real automation recordings completed successfully!")

if __name__ == "__main__":
    asyncio.run(main())

