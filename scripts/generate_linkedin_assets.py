import os
import base64
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT = Path("/home/ahmad10raza/Documents/Mastering/JobPilot")
OUT_DIR = ROOT / "assets" / "linkedin"
OUT_DIR.mkdir(parents=True, exist_ok=True)

# Load brand icon
icon_path = ROOT / "docs" / "assets" / "jobpilot_splash.png"
if not icon_path.exists():
    icon_path = ROOT / "docs" / "assets" / "jobpilot-symbol-color.png"

with open(icon_path, "rb") as f:
    icon_b64 = "data:image/png;base64," + base64.b64encode(f.read()).decode("utf-8")

# 1. Dark Logo HTML (400x400)
logo_dark_html = f"""<!DOCTYPE html>
<html>
<head>
<style>
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{
    width: 400px;
    height: 400px;
    background: radial-gradient(circle at center, #1e293b 0%, #0f172a 100%);
    display: flex;
    justify-content: center;
    align-items: center;
    overflow: hidden;
  }}
  .logo {{
    width: 270px;
    height: 270px;
    object-fit: contain;
    filter: drop-shadow(0 12px 24px rgba(0, 0, 0, 0.5));
  }}
</style>
</head>
<body>
  <img src="{icon_b64}" class="logo" />
</body>
</html>"""

# 2. Light/White Logo HTML (400x400)
logo_light_html = f"""<!DOCTYPE html>
<html>
<head>
<style>
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{
    width: 400px;
    height: 400px;
    background: #ffffff;
    display: flex;
    justify-content: center;
    align-items: center;
    overflow: hidden;
  }}
  .logo {{
    width: 270px;
    height: 270px;
    object-fit: contain;
    filter: drop-shadow(0 8px 20px rgba(0, 0, 0, 0.08));
  }}
</style>
</head>
<body>
  <img src="{icon_b64}" class="logo" />
</body>
</html>"""

# 3. LinkedIn Company Banner (1128x191)
banner_html = f"""<!DOCTYPE html>
<html>
<head>
<style>
  @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700;800;900&display=swap');
  * {{ margin: 0; padding: 0; box-sizing: border-box; font-family: 'Inter', -apple-system, sans-serif; }}
  body {{
    width: 1128px;
    height: 191px;
    background: linear-gradient(110deg, #0a0f1d 0%, #0f172a 45%, #162033 100%);
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 0 45px;
    position: relative;
    overflow: hidden;
  }}
  /* Geometric background glow */
  .glow-orange {{
    position: absolute;
    width: 350px;
    height: 350px;
    background: radial-gradient(circle, rgba(255, 95, 21, 0.15) 0%, rgba(255, 95, 21, 0) 70%);
    right: 60px;
    top: -80px;
    pointer-events: none;
  }}
  .glow-cyan {{
    position: absolute;
    width: 300px;
    height: 300px;
    background: radial-gradient(circle, rgba(14, 165, 233, 0.12) 0%, rgba(14, 165, 233, 0) 70%);
    left: 20px;
    bottom: -100px;
    pointer-events: none;
  }}
  .content-left {{
    z-index: 2;
    display: flex;
    flex-direction: column;
    justify-content: center;
  }}
  .badge {{
    display: inline-flex;
    align-items: center;
    gap: 6px;
    background: rgba(255, 95, 21, 0.15);
    border: 1px solid rgba(255, 95, 21, 0.5);
    color: #ff8c42;
    font-size: 9px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 1.5px;
    padding: 3px 10px;
    border-radius: 4px;
    width: fit-content;
    margin-bottom: 6px;
  }}
  .brand-title {{
    display: flex;
    align-items: baseline;
    gap: 12px;
    margin-bottom: 4px;
  }}
  .title-main {{
    font-size: 26px;
    font-weight: 900;
    color: #ffffff;
    letter-spacing: -0.5px;
  }}
  .title-tagline {{
    font-size: 13px;
    font-weight: 600;
    color: #0ea5e9;
    letter-spacing: 0.5px;
  }}
  .pillars {{
    display: flex;
    align-items: center;
    gap: 16px;
    margin-top: 6px;
  }}
  .pillar-item {{
    display: flex;
    align-items: center;
    gap: 5px;
    font-size: 11px;
    color: #cbd5e1;
    font-weight: 500;
  }}
  .pillar-item span {{
    color: #10b981;
    font-weight: 700;
  }}
  .content-right {{
    z-index: 2;
    display: flex;
    align-items: center;
    gap: 20px;
  }}
  .robot-img {{
    height: 145px;
    width: 145px;
    object-fit: contain;
    filter: drop-shadow(0 10px 20px rgba(0, 0, 0, 0.5));
  }}
</style>
</head>
<body>
  <div class="glow-orange"></div>
  <div class="glow-cyan"></div>

  <div class="content-left">
    <div class="badge">Autonomous Career Navigation</div>
    <div class="brand-title">
      <span class="title-main">JobPilot</span>
      <span class="title-tagline">Autonomous Job Applications • Zero-Hallucination Q&A • Direct Recruiter Outreach</span>
    </div>
    <div class="pillars">
      <div class="pillar-item"><span>✓</span> 12-State Universal ATS Engine</div>
      <div class="pillar-item"><span>✓</span> 5-Tier Deterministic Q&A</div>
      <div class="pillar-item"><span>✓</span> 2-Way Gmail & Outreach CRM</div>
      <div class="pillar-item"><span>✓</span> 100% Local Privacy (AES-256)</div>
    </div>
  </div>

  <div class="content-right">
    <img src="{icon_b64}" class="robot-img" />
  </div>
</body>
</html>"""

print("Generating LinkedIn brand assets via Playwright...")
with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    
    # 1. Dark Logo
    page = browser.new_page(viewport={"width": 400, "height": 400})
    page.set_content(logo_dark_html)
    page.screenshot(path=str(OUT_DIR / "linkedin_logo_dark.png"))
    print(f"Saved: {OUT_DIR / 'linkedin_logo_dark.png'}")
    page.close()
    
    # 2. Light Logo
    page = browser.new_page(viewport={"width": 400, "height": 400})
    page.set_content(logo_light_html)
    page.screenshot(path=str(OUT_DIR / "linkedin_logo_light.png"))
    print(f"Saved: {OUT_DIR / 'linkedin_logo_light.png'}")
    page.close()
    
    # 3. Company Banner
    page = browser.new_page(viewport={"width": 1128, "height": 191})
    page.set_content(banner_html)
    page.screenshot(path=str(OUT_DIR / "linkedin_banner.png"))
    print(f"Saved: {OUT_DIR / 'linkedin_banner.png'}")
    page.close()
    
    browser.close()

print("All LinkedIn assets generated successfully.")

