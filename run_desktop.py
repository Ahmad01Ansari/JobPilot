#!/usr/bin/env python3
"""JobPilot Desktop Application root launcher."""

import os
os.environ["JOBPILOT_DESKTOP"] = "1"

# Ensure valid CA bundle for Python SSL/TLS
try:
    import certifi
    if not os.environ.get("SSL_CERT_FILE"):
        os.environ["SSL_CERT_FILE"] = certifi.where()
    if not os.environ.get("REQUESTS_CA_BUNDLE"):
        os.environ["REQUESTS_CA_BUNDLE"] = certifi.where()
except Exception:
    pass

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
