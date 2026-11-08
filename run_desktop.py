#!/usr/bin/env python3
"""JobPilot Desktop Application root launcher."""

import sys
import os
import io
import subprocess
from pathlib import Path

# Prevent 'NoneType' object has no attribute 'write' in frozen GUI builds on Windows
class _SafeStream:
    def write(self, s: str) -> int:
        return len(s) if s else 0
    def flush(self) -> None:
        pass
    def isatty(self) -> bool:
        return False

if sys.stdout is None or not hasattr(sys.stdout, "write"):
    sys.stdout = _SafeStream()
if sys.stderr is None or not hasattr(sys.stderr, "write"):
    sys.stderr = _SafeStream()
if sys.stdin is None:
    sys.stdin = io.StringIO()

def _ensure_venv() -> None:
    """Auto-detect and switch to the project .venv if run with an unconfigured system Python."""
    if os.environ.get("_JOBPILOT_VENV_BOOTSTRAPPED"):
        return

    root_dir = Path(__file__).resolve().parent
    venv_dir = root_dir / ".venv"
    if not venv_dir.is_dir():
        return

    try:
        if Path(sys.prefix).resolve() == venv_dir.resolve():
            return
    except Exception:
        pass

    if sys.platform == "win32":
        venv_python = venv_dir / "Scripts" / "python.exe"
    else:
        venv_python = venv_dir / "bin" / "python"

    if venv_python.is_file():
        env = dict(os.environ)
        env["_JOBPILOT_VENV_BOOTSTRAPPED"] = "1"
        try:
            code = subprocess.call([str(venv_python)] + sys.argv, env=env)
            sys.exit(code)
        except Exception:
            pass


_ensure_venv()

try:
    from app.main import main
except ModuleNotFoundError as _err:
    print(
        f"\n[JobPilot] Startup Error: Missing dependency '{_err.name}'.\n"
        "Please ensure the virtual environment is activated before running:\n"
        "  Windows PowerShell:  .venv\\Scripts\\Activate.ps1\n"
        "  Command Prompt:      .venv\\Scripts\\activate.bat\n"
        "  Linux/macOS:         source .venv/bin/activate\n"
        "Or run directly with:\n"
        "  .venv\\Scripts\\python run_desktop.py\n",
        file=sys.stderr,
    )
    sys.exit(1)

if __name__ == "__main__":
    sys.exit(main())
