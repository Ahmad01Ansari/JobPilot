import subprocess
from pathlib import Path

ROOT = Path("/home/ahmad10raza/Documents/Mastering/JobPilot")
SRC_DIR = ROOT / "assets" / "demo"
OUT_DIR = ROOT / "website" / "public" / "videos"
OUT_DIR.mkdir(parents=True, exist_ok=True)

DEMOS = [
    {
        "src": SRC_DIR / "ats_demo_v2.mp4",
        "mp4_out": OUT_DIR / "demo-universal-ats.mp4",
        "gif_out": OUT_DIR / "demo-universal-ats.gif",
        "name": "Universal ATS"
    },
    {
        "src": SRC_DIR / "foundit_demo_v2.mp4",
        "mp4_out": OUT_DIR / "demo-foundit.mp4",
        "gif_out": OUT_DIR / "demo-foundit.gif",
        "name": "Foundit Flow Detector"
    },
    {
        "src": SRC_DIR / "naukri_demo_v2.mp4",
        "mp4_out": OUT_DIR / "demo-naukri.mp4",
        "gif_out": OUT_DIR / "demo-naukri.gif",
        "name": "Naukri Direct Apply"
    },
    {
        "src": SRC_DIR / "indeed_demo_v2.mp4",
        "mp4_out": OUT_DIR / "demo-indeed.mp4",
        "gif_out": OUT_DIR / "demo-indeed.gif",
        "name": "Indeed & Glassdoor"
    },
]

def convert_demo(item):
    src = item["src"]
    mp4_out = item["mp4_out"]
    gif_out = item["gif_out"]
    name = item["name"]

    print(f"\n==========================================")
    print(f"Processing: {name} ({src.name})")
    print(f"Original size: {src.stat().st_size / (1024*1024):.2f} MB")

    # 1. Ultra-lightweight Web MP4 (H.264, 720p, CRF 28, preset slow, silent, faststart)
    print(f"--> Encoding lightweight MP4: {mp4_out.name}...")
    cmd_mp4 = [
        "ffmpeg", "-y",
        "-i", str(src),
        "-vf", "scale=1280:-2",
        "-c:v", "libx264",
        "-crf", "28",
        "-preset", "slow",
        "-r", "24",
        "-an",
        "-movflags", "+faststart",
        "-pix_fmt", "yuv420p",
        str(mp4_out)
    ]
    subprocess.run(cmd_mp4, check=True)
    mp4_size_mb = mp4_out.stat().st_size / (1024 * 1024)
    print(f"  [OK] MP4 size: {mp4_size_mb:.2f} MB")

    # 2. Optimized Animated GIF (640px, 10fps, 128 colors palettegen + bayer)
    print(f"--> Encoding lightweight GIF: {gif_out.name}...")
    cmd_gif = [
        "ffmpeg", "-y",
        "-i", str(src),
        "-vf", "fps=10,scale=720:-1:flags=lanczos,split[s0][s1];[s0]palettegen=max_colors=128[p];[s1][p]paletteuse=dither=bayer",
        str(gif_out)
    ]
    subprocess.run(cmd_gif, check=True)
    gif_size_mb = gif_out.stat().st_size / (1024 * 1024)
    print(f"  [OK] GIF size: {gif_size_mb:.2f} MB")

def main():
    for item in DEMOS:
        convert_demo(item)

    print("\n==========================================")
    print("All 4 demos converted successfully!")
    for item in DEMOS:
        mp4_mb = item["mp4_out"].stat().st_size / (1024*1024)
        gif_mb = item["gif_out"].stat().st_size / (1024*1024)
        print(f"  - {item['name']}: MP4 = {mp4_mb:.2f} MB | GIF = {gif_mb:.2f} MB")

if __name__ == "__main__":
    main()

