# Contributing to JobPilot

Welcome to JobPilot! We welcome contributions from developers across all platforms. This guide will help you set up your local development environment on **Windows** or **Ubuntu/Linux**, follow our cross-platform engineering standards, and submit clean Pull Requests.

---

## 1. Core Principles & Cross-Platform Parity

JobPilot runs on both **Ubuntu/Linux** and **Windows**. When writing code:
- **Never hardcode path dividers (`/` or `\\`):** Always use `pathlib.Path` or `os.path.join()`.
- **Never assume POSIX-only commands:** Tools like `xdg-open`, `chmod`, `kill -9` do not work on Windows. Use `SystemService` and `ProcessManager`.
- **Line endings (`CRLF` vs `LF`):** Repository line endings are managed by `.gitattributes`. Shell scripts (`*.sh`) must use LF endings; batch files (`*.bat`) use CRLF.
- **Do not commit secrets:** Never commit `.env`, `secrets.py`, SQLite database files (`*.db`), or personal resumes.

---

## 2. Environment Setup

### Prerequisites
- **Python 3.11** (Recommended 64-bit)
- **Git**
- **Google Chrome** (or Edge/Chromium) for browser automation

---

### Setup on Windows (PowerShell or Command Prompt)

```powershell
# 1. Clone your fork
git clone https://github.com/<your-username>/JobPilot.git
cd JobPilot

# 2. Create and activate a Python 3.11 virtual environment
python -m venv .venv
.venv\Scripts\activate

# 3. Upgrade pip and install dependencies
python -m pip install --upgrade pip
pip install -r requirements.txt

# 4. Verify installation
python run_desktop.py --offscreen --test-run
```

---

### Setup on Ubuntu / Linux (Bash)

```bash
# 1. Clone your fork
git clone https://github.com/<your-username>/JobPilot.git
cd JobPilot

# 2. Install system libraries (for PySide6 and packaging)
sudo apt-get update
sudo apt-get install -y python3.11 python3.11-venv python3-pip libfuse2 libgl1-mesa-glx

# 3. Create and activate virtual environment
python3.11 -m venv .venv
source .venv/bin/activate

# 4. Upgrade pip and install dependencies
pip install --upgrade pip
pip install -r requirements.txt

# 5. Verify installation
python run_desktop.py --offscreen --test-run
```

---

## 3. Pre-Flight Verification Gates

Before pushing code or submitting a PR, your changes must pass the **3 Pre-Flight Gates**:

### Gate 1: Syntax & Compilation
Ensure all modules compile without syntax errors:
```bash
# Linux:
.venv/bin/python -m py_compile runAiBot.py run_desktop.py app.py config/*.py modules/*.py platforms/*.py tests/*.py

# Windows:
.venv\Scripts\python.exe -m py_compile runAiBot.py run_desktop.py app.py config\*.py modules\*.py platforms\*.py tests\*.py
```

### Gate 2: Automated Unit Tests
Run the test suite:
```bash
# Linux:
.venv/bin/python -m unittest discover -s tests

# Windows:
.venv\Scripts\python.exe -m unittest discover -s tests
```

### Gate 3: Headless Desktop GUI Self-Test
Verifies that all PySide6 UI views, theme tokens, and dialogs instantiate cleanly:
```bash
# Linux:
.venv/bin/python run_desktop.py --offscreen --test-run

# Windows:
.venv\Scripts\python.exe run_desktop.py --offscreen --test-run
```

---

## 4. Building Desktop Packages Locally

JobPilot provides automated build scripts for both platforms:

### Building on Windows (`.exe` in `.zip`)
Run the Windows build batch script:
```cmd
scripts\build_windows.bat
```
This produces a complete bundle in `dist\JobPilot-v<VERSION>-windows-x64.zip`.

### Building on Linux (`AppImage`, `.deb`, `.tar.gz`)
Make the script executable and run:
```bash
chmod +x scripts/build_linux.sh
./scripts/build_linux.sh
```
This creates:
- `dist/JobPilot-v<VERSION>-x86_64.AppImage`
- `dist/jobpilot_<VERSION>_amd64.deb`
- `dist/JobPilot-v<VERSION>-linux-x86_64.tar.gz`

---

## 5. Contribution Workflow & PR Guidelines

1. **Create a Feature Branch:**
   ```bash
   git checkout -b feat/my-new-feature
   # or
   git checkout -b fix/issue-description
   ```

2. **Commit Hygiene:**
   - Use [Conventional Commits](https://www.conventionalcommits.org/):
     - `feat:` for new capabilities
     - `fix:` for bug fixes
     - `refactor:` for code restructuring without behavioral change
     - `test:` for test additions/updates
     - `docs:` for documentation updates
   - Write clear, concise commit messages.

3. **Do NOT Create Release Tags:**
   - Regular PRs must **never** create git tags (`v*`).
   - Tags trigger expensive cross-platform GitHub Actions workflows that deplete monthly quota.
   - Version bumps and tagging are reserved for authorized maintainer releases.

4. **Submit your Pull Request:**
   - Push your branch to your fork on GitHub.
   - Open a PR against `main`.
   - Fill out the provided PR checklist completely.
