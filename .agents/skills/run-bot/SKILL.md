---
name: run-bot
description: >-
  Pre-flight checks, status validation, and execution instructions for running the JobPilot
  multi-platform bot and Flask dashboard. Use when running, debugging, or verifying the bot.
---

# Run Bot Skill

## Pre-flight Checklist
1. **Virtual Environment**:
   Verify that `.venv/bin/python` is available and runs Python 3.11:
   ```bash
   .venv/bin/python --version
   ```
2. **Chrome Profile Lock**:
   Ensure no lingering Google Chrome processes are holding a lock on the profile:
   ```bash
   pgrep -a chrome | grep -E "jobpilot.*profile|apply-and-pray.*profile" || echo "Profile clear"
   ```
3. **Compilation Check**:
   Confirm there are no syntax errors:
   ```bash
   .venv/bin/python -m py_compile runAiBot.py app.py config/*.py modules/*.py
   ```
4. **Configuration**:
   Ensure `config/profile.json` exists and candidate data/search settings are defined.

## Execution
- **Run the LinkedIn Bot:**
  ```bash
  .venv/bin/python runAiBot.py
  ```
- **Run the Dashboard:**
  ```bash
  .venv/bin/python app.py
  ```
  Access the web interface at `http://localhost:5000`.
