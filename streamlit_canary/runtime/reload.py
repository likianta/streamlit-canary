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

import os
import subprocess
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


def quote_argv(argv: list[str]) -> list[str]:
    """Quote every element for the Windows command line (no-op elsewhere).

    ``os.execv`` on Windows hands its list to the C runtime, which joins the
    items with spaces and does *not* quote them. An argument holding a space
    therefore arrives as several arguments -- a launch like
    ``python -m my.app 'My Title' 8080`` comes back as ``My``, ``Title``,
    ``8080``, and the app parses a command line nobody typed (its ``8080``
    slot finds ``Title``, say). Quoting each element the way a Windows
    command line wants, and letting the runtime join the quoted pieces,
    rebuilds the line this process was started with.
    """
    if os.name != 'nt':
        return argv
    return [subprocess.list2cmdline([arg]) for arg in argv]


def restart_process(delay: float = _DELAY) -> None:
    """Re-execute this process after `delay` seconds (non-blocking).

    The delay gives the "reloading" frame time to reach the browser before
    the socket is torn down.
    """

    def _run() -> None:
        time.sleep(delay)
        argv = original_argv()
        # the image path is handed over as-is -- the runtime resolves it
        # itself -- while the elements go through the shell-quoting above.
        program, argv = argv[0], quote_argv(argv)
        try:
            os.execv(program, argv)
        except OSError as exc:  # pragma: no cover - best effort
            # `print` is monkey-patched by neoprint in this package (it
            # rejects `flush=...`), so write straight to stderr.
            sys.stderr.write(f'[streamlit-canary] rerun failed: {exc}\n')
            sys.stderr.flush()

    threading.Thread(target=_run, name='sc-rerun', daemon=True).start()
