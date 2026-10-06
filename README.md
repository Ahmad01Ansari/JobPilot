# 🚀 JobPilot

> **The unified, autonomous job application cockpit (LinkedIn, Naukri, Indeed, Glassdoor, Foundit, and Universal ATS portals) featuring an intelligent PySide6 desktop suite, multi-tier Q&A reasoning, and automated cross-platform distribution.**

[![Release](https://img.shields.io/badge/Release-v0.1.0--beta.1-orange.svg)](https://github.com/Ahmad01Ansari/JobPilot/releases)
[![Python](https://img.shields.io/badge/Python-3.11-blue.svg)](https://www.python.org/downloads/release/python-3110/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Platform](https://img.shields.io/badge/Platform-Windows%20%7C%20Ubuntu%20Linux-lightgrey.svg)](#downloads--installation)

---

## 📥 Downloads & Installation

Pre-built binaries for **Windows 10/11** and **Ubuntu/Linux** are published with every release under [GitHub Releases](../../releases).

### 🐧 Ubuntu / Debian Linux

#### Option A: Debian Package (`.deb`) — *Recommended*
Installs system-wide with desktop application launcher and brand icons:
```bash
# Install via apt (handles dependencies automatically)
sudo apt install ./jobpilot_0.1.0-beta.1_amd64.deb

# Or install via dpkg
sudo dpkg -i jobpilot_0.1.0-beta.1_amd64.deb
sudo apt-get install -f
```
Launch directly from your application menu or via terminal:
```bash
jobpilot
```

#### Option B: Standalone AppImage
Runs on any modern 64-bit Linux distribution with zero system installation:
```bash
chmod +x JobPilot-0.1.0-beta.1-x86_64.AppImage
./JobPilot-0.1.0-beta.1-x86_64.AppImage
```

---

### 🪟 Windows 10 / 11

1. Download **`JobPilot-v0.1.0-beta.1-windows-x64.zip`** from [Releases](../../releases).
2. Extract the ZIP archive to a folder (e.g., `C:\Program Files\JobPilot` or your Documents).
3. Double-click **`JobPilot.exe`** to launch the Desktop application.

---

## ⚡ What JobPilot Does

- **Comprehensive Desktop Cockpit:** 13-view native PySide6 desktop suite featuring dark/light adaptive tokens, real-time observability timeline, and system tray integration.
- **Multi-Platform Automation:** Native automation engines for **LinkedIn Easy Apply**, **Naukri.com**, **Indeed**, **Glassdoor**, **Foundit**, and external ATS portals (**Greenhouse**, **Lever**, **Workday**, **Ashby**).
- **Multi-Tier Q&A Knowledge Base:** 300+ canonical screening questions with verified candidate facts (`PROFILE_FACT`, `RESUME_FACT`, `QNA_RULE`) ensuring zero hallucination.
- **Cross-Platform Deduplication:** Conservative deduplication preserving raw portal listings while tracking logical opportunities across portals to avoid duplicate submissions.
- **Cooperative Human Checkpoints:** Never attempts automated CAPTCHA bypass or fingerprint spoofing. Pauses safely when OTP, verification challenges, or unknown fields occur so you retain full control.
- **Sanitized Observability:** Real-time log cockpit and one-click diagnostic reports with automated redaction of API keys, cookies, and tokens via `LogSanitizer`.

---

## 🛠️ Running from Source (Development)

### Requirements
- **Python 3.11.x**
- **Google Chrome** (latest stable release)
- **Linux** (Ubuntu 22.04/24.04 LTS) or **Windows 10/11**

### 1. Clone & Set Up Virtual Environment

```bash
# Linux
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

# Windows (Command Prompt / PowerShell)
py -3.11 -m venv .venv
.venv\Scripts\activate
pip install --upgrade pip
pip install -r requirements.txt
```

### 2. Launch the Desktop Application

```bash
# Linux
.venv/bin/python run_desktop.py

# Windows
python run_desktop.py
```
*If running for the first time, the Onboarding Wizard will guide you through AI connection, resume import, profile review, and platform setup.*

### 3. Alternative Interfaces

```bash
# Flask Web Management Dashboard (http://localhost:5000)
python app.py

# Standalone First-Run Setup Wizard
python run_wizard.py

# Headless GUI Self-Test (Verification)
python run_desktop.py --offscreen --test-run

# Run Platform Automation directly via CLI
python runAiBot.py --platform linkedin
python runAiBot.py --platform naukri
python runAiBot.py --platform indeed
python runAiBot.py --platform glassdoor
python runAiBot.py --platform foundit
```

---

## 🏗️ Building Distribution Packages Locally

### On Linux (AppImage, `.deb`, and `.tar.gz`)
Run the automated packaging script:
```bash
chmod +x scripts/build_linux.sh
./scripts/build_linux.sh
```
Outputs are generated in `dist/`:
- `dist/JobPilot-0.1.0-beta.1-x86_64.AppImage`
- `dist/jobpilot_0.1.0-beta.1_amd64.deb`
- `dist/jobpilot-v0.1.0-beta.1-linux-x86_64.tar.gz`

### On Windows (`.zip`)
Run the Windows batch build script:
```cmd
scripts\build_windows.bat
```
Output is generated in `dist\JobPilot-v0.1.0-beta.1-windows-x64.zip`.

---

## 🚀 Automated GitHub Releases CI/CD

JobPilot includes a complete GitHub Actions release pipeline (`.github/workflows/release.yml`).

### How to Cut a Release
Pushing a git version tag triggers parallel Windows and Ubuntu runners to compile and publish a GitHub Release with all binary assets attached:

```bash
# Tag a release commit
git tag -a v0.1.0-beta.1 -m "Release v0.1.0-beta.1"

# Push the tag to GitHub
git push origin v0.1.0-beta.1
```

The GitHub Actions workflow will automatically:
1. Build Windows executable and compress it to `JobPilot-v0.1.0-beta.1-windows-x64.zip`.
2. Build Linux binaries and produce `JobPilot-0.1.0-beta.1-x86_64.AppImage`, `jobpilot_0.1.0-beta.1_amd64.deb`, and `tar.gz`.
3. Create a GitHub Release under `v0.1.0-beta.1` and upload all artifacts.

---

## 🧪 Testing & Verification

Run the comprehensive unit test suite:
```bash
# Automated discovery
.venv/bin/python -m unittest discover -s tests

# Pre-flight diagnostic & security test
.venv/bin/python -m unittest tests/test_beta_readiness_diagnostics.py tests/test_security_hardening.py
```

---

## ⚠️ Disclaimer

JobPilot is intended for personal job search automation and workflow acceleration. You are responsible for complying with the Terms of Service of each respective platform and for reviewing all submitted application details.
