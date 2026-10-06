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
from collections import deque
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw, ImageFilter


def generate_all_icons(source_path: Path = Path("JobPilot.png"), project_root: Path = Path(".")) -> None:
    if not source_path.exists():
        print(f"Error: Source image not found at {source_path}")
        sys.exit(1)

    brand_dir = project_root / "app" / "ui" / "assets" / "brand"
    brand_dir.mkdir(parents=True, exist_ok=True)

    src = Image.open(source_path).convert("RGB")
    w, h = src.size
    arr = np.array(src, dtype=np.float32)

    # 1. Flood fill pitch-black background outside the squircle
    is_black = np.all(arr <= 4, axis=2)
    mask = np.ones((h, w), dtype=np.uint8) * 255
    q = deque([(0, 0), (w - 1, 0), (0, h - 1), (w - 1, h - 1)])
    visited = np.zeros((h, w), dtype=bool)
    for x, y in q:
        visited[y, x] = True

    while q:
        x, y = q.popleft()
        mask[y, x] = 0
        for dx, dy in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
            nx, ny = x + dx, y + dy
            if 0 <= nx < w and 0 <= ny < h and not visited[ny, nx]:
                visited[ny, nx] = True
                if is_black[ny, nx]:
                    q.append((nx, ny))

    # Anti-alias mask edge
    mask_img = Image.fromarray(mask, mode="L")
    mask_blur = mask_img.filter(ImageFilter.GaussianBlur(radius=1.5))

    # Composite onto transparent RGBA
    rgba = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    rgba.paste(src, (0, 0), mask=mask_blur)

    # Balanced square crop
    y_indices, x_indices = np.where(mask == 255)
    min_x, max_x = x_indices.min(), x_indices.max()
    min_y, max_y = y_indices.min(), y_indices.max()

    cx = (min_x + max_x) // 2
    cy = (min_y + max_y) // 2
    half_size = max(max_x - min_x, max_y - min_y) // 2 + 20

    crop_box = (cx - half_size, cy - half_size, cx + half_size, cy + half_size)
    cropped = rgba.crop(crop_box)

    # Master 512x512
    master_512 = cropped.resize((512, 512), Image.Resampling.LANCZOS)
    master_512.save(brand_dir / "jobpilot_512.png", "PNG", optimize=True)
    master_512.save(brand_dir / "jobpilot.png", "PNG", optimize=True)

    # Multi-resolution PNGs
    sizes = [256, 128, 64, 48, 32, 24, 16]
    for s in sizes:
        resized = master_512.resize((s, s), Image.Resampling.LANCZOS)
        resized.save(brand_dir / f"jobpilot_{s}.png", "PNG", optimize=True)

    # Windows .ico
    master_512.save(
        brand_dir / "jobpilot.ico",
        format="ICO",
        sizes=[(256, 256), (128, 128), (64, 64), (48, 48), (32, 32), (24, 24), (16, 16)],
    )

    # Tray Icons (32x32)
    tray_32 = master_512.resize((32, 32), Image.Resampling.LANCZOS)
    tray_32.save(brand_dir / "jobpilot_tray.png", "PNG", optimize=True)

    tray_active = tray_32.copy()
    draw = ImageDraw.Draw(tray_active)
    draw.ellipse([22, 22, 31, 31], fill=(22, 27, 34, 255), outline=(15, 17, 23, 255))
    draw.ellipse([24, 24, 29, 29], fill=(46, 160, 67, 255))
    tray_active.save(brand_dir / "jobpilot_tray_active.png", "PNG", optimize=True)

    # Avatar Badge (Tight crop on robot face)
    head_crop = master_512.crop((120, 100, 392, 372))
    head_badge = head_crop.resize((64, 64), Image.Resampling.LANCZOS)
    head_badge.save(brand_dir / "jobpilot_badge.png", "PNG", optimize=True)

    # Tray avatar
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
