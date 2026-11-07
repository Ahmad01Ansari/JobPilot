#!/usr/bin/env python3
"""Centralized Icon & Brand Asset Generator for JobPilot.

Generates high-resolution multi-platform icons from JobPilot.png:
- Windows multi-resolution icon (jobpilot.ico: 16, 24, 32, 48, 64, 128, 256)
- Standard resolution PNG icons (jobpilot_512.png ... jobpilot_16.png)
- System tray icons (jobpilot_tray.png, jobpilot_tray_active.png, avatar variants)
- App brand badge / avatar (jobpilot_badge.png)
- Web dashboard favicon and icons
- Linux desktop launcher entry
"""

import sys
from pathlib import Path
from PIL import Image, ImageDraw


def generate_all_icons(source_path: Path = Path("JobPilot.png"), project_root: Path = Path(".")) -> None:
    if not source_path.exists():
        print(f"Error: Source image not found at {source_path}")
        sys.exit(1)

    brand_dir = project_root / "app" / "ui" / "assets" / "brand"
    brand_dir.mkdir(parents=True, exist_ok=True)

    src = Image.open(source_path).convert("RGBA")
    w, h = src.size

    # Master 512x512
    master_512 = src.resize((512, 512), Image.Resampling.LANCZOS)
    master_512.save(brand_dir / "jobpilot_512.png", "PNG", optimize=True)
    master_512.save(brand_dir / "jobpilot.png", "PNG", optimize=True)

    # Multi-resolution PNGs
    sizes = [256, 128, 64, 48, 32, 24, 16]
    for s in sizes:
        resized = master_512.resize((s, s), Image.Resampling.LANCZOS)
        resized.save(brand_dir / f"jobpilot_{s}.png", "PNG", optimize=True)

    # Windows .ico containing all standard shell sizes
    master_512.save(
        brand_dir / "jobpilot.ico",
        format="ICO",
        sizes=[(256, 256), (128, 128), (64, 64), (48, 48), (32, 32), (24, 24), (16, 16)],
    )

    # System Tray Icons (32x32)
    tray_32 = master_512.resize((32, 32), Image.Resampling.LANCZOS)
    tray_32.save(brand_dir / "jobpilot_tray.png", "PNG", optimize=True)

    # Tray Active Icon (with high-visibility active green dot in bottom-right)
    tray_active = tray_32.copy()
    draw = ImageDraw.Draw(tray_active)
    draw.ellipse([22, 22, 31, 31], fill=(22, 27, 34, 255), outline=(15, 17, 23, 255))
    draw.ellipse([24, 24, 29, 29], fill=(46, 160, 67, 255))
    tray_active.save(brand_dir / "jobpilot_tray_active.png", "PNG", optimize=True)

    # Avatar Badge (Tight crop on robot face & visor)
    # Head and headphones span X: 96..384, Y: 70..358 on 512x512 canvas
    head_crop = master_512.crop((96, 70, 384, 358))
    head_badge = head_crop.resize((64, 64), Image.Resampling.LANCZOS)
    head_badge.save(brand_dir / "jobpilot_badge.png", "PNG", optimize=True)

    # Tray Avatar
    tray_avatar = head_badge.resize((32, 32), Image.Resampling.LANCZOS)
    tray_avatar.save(brand_dir / "jobpilot_tray_avatar.png", "PNG", optimize=True)

    tray_avatar_active = tray_avatar.copy()
    draw_av = ImageDraw.Draw(tray_avatar_active)
    draw_av.ellipse([22, 22, 31, 31], fill=(22, 27, 34, 255), outline=(15, 17, 23, 255))
    draw_av.ellipse([24, 24, 29, 29], fill=(46, 160, 67, 255))
    tray_avatar_active.save(brand_dir / "jobpilot_tray_avatar_active.png", "PNG", optimize=True)

    # Web Dashboard Static Assets
    static_img = project_root / "static" / "img"
    static_img.mkdir(parents=True, exist_ok=True)
    master_512.save(static_img / "jobpilot.png", "PNG", optimize=True)
    master_512.save(project_root / "static" / "favicon.ico", format="ICO", sizes=[(32, 32), (16, 16)])

    # Linux Desktop Entry
    desktop_entry = f"""[Desktop Entry]
Version=1.0
Type=Application
Name=JobPilot
Comment=Desktop Job Automation & Multi-Platform Application Bot
Exec=python3 {project_root.resolve() / 'run_desktop.py'}
Icon={(brand_dir / 'jobpilot_256.png').resolve()}
Terminal=false
Categories=Utility;Office;Development;
StartupWMClass=JobPilot
"""
    desktop_file = project_root / "scripts" / "jobpilot.desktop"
    desktop_file.parent.mkdir(parents=True, exist_ok=True)
    desktop_file.write_text(desktop_entry, encoding="utf-8")

    print(f"Successfully generated all JobPilot icon assets in {brand_dir}!")


if __name__ == "__main__":
    generate_all_icons()
