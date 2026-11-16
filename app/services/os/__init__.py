"""Operating System abstraction and platform infrastructure services."""

from app.services.os.app_paths import AppPaths
from app.services.os.system_service import SystemService
from app.services.os.process_manager import ProcessManager
from app.services.os.crash_reporter import install_global_crash_handler
from app.services.os.lifecycle_manager import ApplicationLifecycleManager
from app.services.os.compatibility import apply_runtime_compatibility_patches

__all__ = [
    "AppPaths",
    "SystemService",
    "ProcessManager",
    "install_global_crash_handler",
    "ApplicationLifecycleManager",
    "apply_runtime_compatibility_patches",
]
