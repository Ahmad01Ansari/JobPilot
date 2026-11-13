"""Runtime compatibility and interpreter normalization for modern Python environments."""

import sys


def apply_runtime_compatibility_patches() -> None:
    """Applies compatibility shims for known runtime and interpreter issues.

    1. Python 3.15+ lazy import normalization:
       In Python 3.15, standard library `concurrent.futures` uses lazy imports
       (`lazy from .thread import ThreadPoolExecutor`). Under certain bytecode
       caching and namespace conditions, `asyncio.to_thread` / `run_in_executor`
       fails with `TypeError: 'lazy_import' object is not callable` when polling
       CDP ports (e.g. Stagehand's _chrome_debugging_ready). Eagerly binding
       ThreadPoolExecutor and ProcessPoolExecutor resolves the lazy imports.

    2. Python 3.13+ removal of `cgi`:
       In Python 3.13+, standard library `cgi` was removed (PEP 594).
       When `legacy_cgi` is installed, map it into `sys.modules["cgi"]` so legacy
       multipart form parsing and harness utilities operate seamlessly.
    """
    # 1. Normalize concurrent.futures lazy imports (Python 3.15+)
    try:
        import concurrent.futures.thread
        import concurrent.futures.process
        import concurrent.futures
        concurrent.futures.ThreadPoolExecutor = concurrent.futures.thread.ThreadPoolExecutor
        concurrent.futures.ProcessPoolExecutor = concurrent.futures.process.ProcessPoolExecutor

        try:
            import asyncio.base_events
            asyncio.base_events.concurrent.futures.ThreadPoolExecutor = concurrent.futures.thread.ThreadPoolExecutor
            asyncio.base_events.concurrent.futures.ProcessPoolExecutor = concurrent.futures.process.ProcessPoolExecutor
        except Exception:
            pass
    except Exception:
        pass

    # 2. Provide cgi compatibility if legacy_cgi is available (Python 3.13+)
    if "cgi" not in sys.modules:
        try:
            import cgi  # noqa: F401
        except ModuleNotFoundError:
            try:
                import legacy_cgi
                sys.modules["cgi"] = legacy_cgi
            except ImportError:
                pass


# Apply immediately upon module import
apply_runtime_compatibility_patches()

