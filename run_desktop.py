#!/usr/bin/env python3
"""JobPilot Desktop Application root launcher."""

import os
os.environ["JOBPILOT_DESKTOP"] = "1"

import sys
import io

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

from app.main import main

if __name__ == "__main__":
    sys.exit(main())
