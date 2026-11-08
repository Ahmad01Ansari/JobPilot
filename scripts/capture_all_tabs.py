import os
import sys
import time
from pathlib import Path

# Configure widescreen offscreen virtual display
os.environ["QT_QPA_PLATFORM"] = "offscreen:size=1600x1000"
os.environ["JOBPILOT_TEST_RUN"] = "1"

ROOT = Path("/home/ahmad10raza/Documents/Mastering/JobPilot")
sys.path.insert(0, str(ROOT))

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap

from app.ui.main_window import MainWindow
from app.ui.theme import ThemeManager
from app.ui.navigation import NAV_ITEMS

app = QApplication.instance()
if not app:
    app = QApplication(sys.argv)

ThemeManager.apply_dark_theme(app)

window = MainWindow()
window.setWindowState(Qt.WindowNoState)
window.setFixedSize(1600, 1000)
window.show()

# Process initial events
for _ in range(20):
    app.processEvents()
    time.sleep(0.04)

output_dir = ROOT / "docs" / "assets"
output_dir.mkdir(parents=True, exist_ok=True)

print("Starting full 1600x1000 tab capture across all registered views...")

for item in NAV_ITEMS:
    print(f"Navigating to tab: {item.id} ({item.title})...")
    window.navigate_to(item.id)
    
    # Process events to allow view to populate and repaint
    for _ in range(25):
        app.processEvents()
        time.sleep(0.04)
        
    pixmap = window.grab()
    out_file = output_dir / f"screenshot_{item.id}.png"
    pixmap.save(str(out_file), "PNG")
    print(f"  [OK] Saved: {out_file.name} ({out_file.stat().st_size:,} bytes, {pixmap.width()}x{pixmap.height()})")

# Also capture full window on dashboard as main window
window.navigate_to("dashboard")
for _ in range(20):
    app.processEvents()
    time.sleep(0.04)
window.grab().save(str(output_dir / "screenshot_main_window.png"), "PNG")

print("\nAll 14 widescreen tab screenshots captured successfully at 1600x1000.")
sys.exit(0)
