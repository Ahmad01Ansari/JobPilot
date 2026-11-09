import os
import subprocess
import math
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

ROOT = Path("/home/ahmad10raza/Documents/Mastering/JobPilot")
SCREENS_DIR = ROOT / "website" / "public" / "screens"
VIDEOS_DIR = ROOT / "website" / "public" / "videos"
VIDEOS_DIR.mkdir(parents=True, exist_ok=True)

DEMOS = [
    {
        "id": "demo-universal-ats",
        "screen": "screenshot_automation.png",
        "title": "Universal ATS State Machine",
        "target": "CloudScale Systems (Greenhouse ATS)",
        "fields": ["Name: Ahmad Raza", "Email: rjaahmad60@gmail.com", "Tenure: 7 Years [RESUME_FACT]"],
        "checkpoint": "Human Checkpoint: Salary Approved ($175k)",
    },
    {
        "id": "demo-linkedin",
        "screen": "screenshot_jobs.png",
        "title": "LinkedIn Easy Apply Engine",
        "target": "Senior Backend Architect (Easy Apply)",
        "fields": ["Contact Verified", "Attached: Ahmad_Raza_Systems.pdf", "Visa Sponsorship: No [QNA_RULE]"],
        "checkpoint": "Pre-flight Rate Limit: 5/15 Safe",
    },
    {
        "id": "demo-naukri",
        "screen": "screenshot_platforms.png",
        "title": "Naukri Direct Apply & Safety Gate",
        "target": "Lead Infrastructure Engineer",
        "fields": ["Session Keyring: Valid", "Notice Period: 30 Days", "Current CTC: In Range"],
        "checkpoint": "Popup Dismissed & Quota Safe",
    },
    {
        "id": "demo-indeed",
        "screen": "screenshot_applications.png",
        "title": "Indeed & Glassdoor Submitter",
        "target": "Distributed Systems Developer",
        "fields": ["Router: External ATS Forwarded", "Page 1: Qualifications Complete", "Delays: Humanized (2.4s)"],
        "checkpoint": "Zero Bot Bypass • Anti-Detection On",
    },
]

W, H = 1280, 800
FPS = 24
TOTAL_FRAMES = 120  # 5 seconds loop

def create_demo_video(spec):
    out_mp4 = VIDEOS_DIR / f"{spec['id']}.mp4"
    screen_path = SCREENS_DIR / spec["screen"]
    if not screen_path.exists():
        print(f"Missing screen {screen_path}")
        return

    base_img = Image.open(screen_path).convert("RGBA").resize((W, H), Image.Resampling.LANCZOS)
    
    ffmpeg_cmd = [
        "ffmpeg", "-y",
        "-f", "image2pipe",
        "-vcodec", "png",
        "-r", str(FPS),
        "-i", "-",
        "-c:v", "libx264",
        "-pix_fmt", "yuv420p",
        "-crf", "22",
        str(out_mp4)
    ]
    
    proc = subprocess.Popen(ffmpeg_cmd, stdin=subprocess.PIPE)

    for i in range(TOTAL_FRAMES):
        t = i / TOTAL_FRAMES
        frame = base_img.copy()
        draw = ImageDraw.Draw(frame)

        # 1. Animated Scanline moving down
        scan_y = int((t * 2 % 1.0) * H)
        draw.line([(0, scan_y), (W, scan_y)], fill=(255, 95, 21, 180), width=3)
        draw.line([(0, max(0, scan_y - 2)), (W, max(0, scan_y - 2))], fill=(255, 140, 50, 80), width=4)

        # 2. Animated Cursor moving to form
        cx = int(250 + math.sin(t * math.pi * 2) * 120 + t * 200)
        cy = int(220 + math.cos(t * math.pi * 2) * 80 + t * 150)
        # Draw target reticle
        draw.ellipse([cx - 15, cy - 15, cx + 15, cy + 15], outline=(14, 165, 233, 220), width=2)
        draw.line([cx - 20, cy, cx + 20, cy], fill=(14, 165, 233, 200), width=1)
        draw.line([cx, cy - 20, cx, cy + 20], fill=(14, 165, 233, 200), width=1)
        draw.ellipse([cx - 3, cy - 3, cx + 3, cy + 3], fill=(255, 95, 21, 255))

        # 3. Live Floating Automation Telemetry Box (bottom-left)
        bx, by, bw, bh = 40, H - 170, 480, 130
        draw.rectangle([bx, by, bx + bw, by + bh], fill=(15, 17, 23, 230), outline=(255, 95, 21, 200), width=2)
        
        # Header in telemetry box
        draw.rectangle([bx, by, bx + bw, by + 28], fill=(30, 41, 59, 240))
        draw.text((bx + 12, by + 7), f"AUTONOMOUS RUN: {spec['title']}", fill=(255, 255, 255))
        draw.text((bx + bw - 110, by + 7), "● LIVE STREAM", fill=(16, 185, 129))

        # Target and fields
        draw.text((bx + 12, by + 36), f"Target: {spec['target']}", fill=(14, 165, 233))
        
        # Stepped typing text based on time
        field_idx = min(len(spec["fields"]) - 1, int(t * len(spec["fields"])))
        current_field = spec["fields"][field_idx]
        draw.text((bx + 12, by + 58), f">> Inputting: {current_field}", fill=(248, 250, 252))
        
        # Checkpoint / Status bar
        if t > 0.65:
            draw.rectangle([bx + 12, by + 88, bx + bw - 12, by + 115], fill=(16, 185, 129, 60), outline=(16, 185, 129, 200), width=1)
            draw.text((bx + 20, by + 94), f"VERIFIED: {spec['checkpoint']}", fill=(16, 185, 129))
        else:
            draw.rectangle([bx + 12, by + 88, bx + bw - 12, by + 115], fill=(245, 158, 11, 40), outline=(245, 158, 11, 180), width=1)
            draw.text((bx + 20, by + 94), "STATUS: Resolving Form Inputs...", fill=(245, 158, 11))

        # Write PNG bytes to ffmpeg
        frame.convert("RGB").save(proc.stdin, "PNG")

    proc.stdin.close()
    proc.wait()
    print(f"Generated {out_mp4.name} ({out_mp4.stat().st_size:,} bytes)")

def main():
    print("Starting video demo generation for all 4 automation engines...")
    for spec in DEMOS:
        create_demo_video(spec)
    print("All 4 automation demo videos generated successfully!")

if __name__ == "__main__":
    main()

