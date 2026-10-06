"""JobPilot Desktop Application Package."""
import os
import importlib.util
from app.version import __version__, VERSION

# Backward compatibility: execute app.py in this package namespace
# so existing tests and scripts (e.g. from app import app, patch("app.tracker")) work seamlessly
_root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_flask_app_file = os.path.join(_root_dir, "app.py")
if os.path.exists(_flask_app_file):
    with open(_flask_app_file, "r", encoding="utf-8") as _f:
        _code = compile(_f.read(), _flask_app_file, "exec")
        exec(_code, globals())


