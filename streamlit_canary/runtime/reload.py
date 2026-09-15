"""Process-level rerun (FastAPI ``--reload`` style).

Why re-execute the interpreter instead of reloading modules in place?

The live objects of a running Starlette/Uvicorn process hold references to
the classes they were built from. Re-importing ``streamlit_canary.*`` in
place therefore produces *two* copies of e.g. ``Property`` / ``Component``,
and every ``isinstance`` check and ``Property`` comparison between old and
new objects silently starts failing. Re-executing the interpreter gives a
guaranteed-fresh import graph, and it also covers added / deleted /
renamed files, which no in-place reloader handles.

State is deliberately not preserved: this is the same contract as
FastAPI's ``--reload`` (``StateV2`` does not survive a rerun).
"""

from __future__ import annotations

import os
import sys
import threading
import time

_DELAY = 0.3


def original_argv() -> list[str]:
    """The command line that started this process.

    ``sys.orig_argv`` (Python >= 3.10) is used when available because it
    also reflects an ``-m`` / ``-X`` style invocation, which ``sys.argv``
    alone cannot reproduce.
    """
    argv = getattr(sys, 'orig_argv', None)
    if argv:
        return list(argv)
    return [sys.executable, *sys.argv]


def restart_process(delay: float = _DELAY) -> None:
    """Re-execute this process after `delay` seconds (non-blocking).

    The delay gives the "reloading" frame time to reach the browser before
    the socket is torn down.
    """

    def _run() -> None:
        time.sleep(delay)
        argv = original_argv()
        try:
            os.execv(argv[0], argv)
        except OSError as exc:  # pragma: no cover - best effort
            # `print` is monkey-patched by neoprint in this package (it
            # rejects `flush=...`), so write straight to stderr.
            sys.stderr.write(f'[streamlit-canary] rerun failed: {exc}\n')
            sys.stderr.flush()

    threading.Thread(target=_run, name='sc-rerun', daemon=True).start()
