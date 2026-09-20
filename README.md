# 🙏 Apply & Pray

> **The AI-powered LinkedIn job application bot for people who are tired of clicking "Easy Apply" like it is a part-time job.**

Applying to jobs is a full-time job. This bot works overtime.

---

## 💀 Why This Exists

At some point, humanity collectively agreed that job seekers should upload a resume, manually retype it, answer the same questions, write cover letters, and repeat until motivation reaches critically low battery mode.

Welcome to **Apply & Pray**.

> Apply. Pray. Repeat. Preferably with fewer clicks.

---

## 🚀 What This Bot Does

The bot can search LinkedIn jobs, read job descriptions, fill application forms, answer repetitive screening questions, upload resumes, generate AI-assisted content when configured, and track application history through a local dashboard.

---

## 📦 Requirements

- **Python 3.11.x**
- **Google Chrome** latest stable version
- **Windows 10/11** recommended
- Internet connection
- LinkedIn account
- Resume PDF

> Python 3.11 is recommended because Selenium and `undetected-chromedriver` are more stable there than on newer bleeding-edge Python versions.

---

## ⚙️ Installation

### 1. Install Python 3.11

Install Python 3.11 and enable **Add Python to PATH**.

Verify:

```powershell
py -3.11 --version
```

### 2. Create a Virtual Environment

```powershell
cd C:\Users\Test\Documents\Apply-and-Pray
py -3.11 -m venv venv
venv\Scripts\activate
python -m pip install --upgrade pip setuptools wheel
```

### 3. Install Dependencies

```powershell
pip install -r requirements.txt
```

### 4. Configure Your Details

Edit these files:

| File | Purpose |
|---|---|
| `config/personals.py` | Personal details used in applications |
| `config/questions.py` | Common screening answers and resume path |
| `config/search.py` | Job filters and preferences |
| `config/secrets.py` | LinkedIn login and optional AI API key |
| `config/settings.py` | Bot behavior, stealth mode, delays, paths |

### 5. Add Your Resume

Place your resume where `default_resume_path` points in `config/questions.py`.

Default example:

```python
default_resume_path = "all resumes/default/resume.pdf"
```

---

## ▶️ Run the Bot

```powershell
python runAiBot.py
```

Before running, close all Chrome windows, keep fewer than 10 tabs open, and make sure Chrome is updated.

---

## 📊 Run the Dashboard

```powershell
python app.py
```

Open:

```text
http://localhost:5000
```

---

## 🧯 Troubleshooting

### ChromeDriver Version Error

If you see `This version of ChromeDriver only supports Chrome version X`, update Chrome from `chrome://settings/help`, close Chrome, and run again.

This build also detects your installed Chrome version and asks `undetected-chromedriver` for a matching driver.

### Chrome Profile Permission Error

This build uses a safer Windows profile path:

```text
%LOCALAPPDATA%\ApplyAndPrayChromeProfile
```

No more fighting `C:\temp` like it owes you money.

---

## ⚠️ Disclaimer

This project is for educational and research purposes only. You are responsible for how you use it and for complying with LinkedIn's Terms of Service and applicable laws.

Use at your own risk.
