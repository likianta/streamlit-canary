"""Watch source folders and tell the runtime when the code changes.

This uses `watchdog`, the same library Streamlit uses, so the behaviour
(and its Windows quirks) are well understood. `watchdog` is an optional
dependency — the same choice Streamlit makes — and watching is simply
disabled when it is missing.

The watcher never reloads anything by itself: it only records *that*
something changed and notifies the runtime, which pushes a "source
changed" notice to the browser. The actual reload happens when the user
clicks the rerun button (see `reload.py`).

Windows note: `ReadDirectoryChangesW` emits spurious events caused by
Windows Defender, the search indexer and OneDrive sync. Streamlit works
around this with mtime + content-hash checks; we use the cheaper
`(mtime_ns, size)` pair plus a short debounce, which is enough to
collapse the burst of events a single editor save produces.
"""

import os
import sys
import threading
import typing as tp
from pathlib import Path

# Only these suffixes trigger a rerun. Editors leave a lot of noise behind
# (`*.tmp`, `*~`, `.#foo`, `*.swp`), and vendored trees churn on their own.
WATCH_SUFFIXES = ('.py', '.pyi', '.css', '.js', '.html')

# Directories that are never interesting to us.
_IGNORED_DIRS = frozenset(
    {
        '__pycache__',
        '.git',
        '.hg',
        '.svn',
        '.venv',
        'venv',
        'node_modules',
        'site-packages',
        'dist-packages',
        '.mypy_cache',
        '.pytest_cache',
        '.ruff_cache',
        '.idea',
        '.vscode',
    }
)

# Seconds to wait before reporting a batch of events, so that the handful
# of events produced by one editor save collapse into one notification.
_DEBOUNCE = 0.15


def _load_watchdog() -> tuple[tp.Any, tp.Any] | None:
    """Import watchdog lazily; returns `(Observer, EventHandlerBase)`.

    Returns None when watchdog is not installed, in which case source
    watching is silently disabled.
    """
    try:
        from watchdog.events import FileSystemEventHandler
        from watchdog.observers import Observer
    except ImportError:  # pragma: no cover - optional dependency
        return None
    return Observer, FileSystemEventHandler


_API = _load_watchdog()
_is_available = _API is not None


# ---------------------------------------------------------------------------
# public registration API
# ---------------------------------------------------------------------------


_extra_folders: list[Path] = []
_extra_files: list[Path] = []


def add_watch_folder(folder: str | os.PathLike) -> None:
    """Watch an additional folder (recursively) for source changes.

    Example:
        >>> import streamlit_canary as sc
        >>> sc.add_watch_folder('./test/pixel_fidelity')
    """
    path = Path(folder).expanduser()
    if path not in _extra_folders:
        _extra_folders.append(path)


def add_watch_file(file: str | os.PathLike) -> None:
    """Watch a single additional file for source changes."""
    path = Path(file).expanduser()
    if path not in _extra_files:
        _extra_files.append(path)


def extra_folders() -> tuple[Path, ...]:
    return tuple(_extra_folders)


def extra_files() -> tuple[Path, ...]:
    return tuple(_extra_files)


def clear_extra_paths() -> None:
    """Forget every `add_watch_folder` / `add_watch_file` registration."""
    _extra_folders.clear()
    _extra_files.clear()


# ---------------------------------------------------------------------------
# default folders
# ---------------------------------------------------------------------------


def _same_or_under(path: Path, root: str) -> bool:
    """Case-insensitive `path` is `root` or lives below it (Windows-safe)."""
    if not root:
        return False
    p = str(path).lower().replace('/', '\\')
    r = str(root).lower().replace('/', '\\')
    return p == r or p.startswith(r + '\\')


def _looks_like_python_install(path: Path) -> bool:
    """Heuristic markers of a stdlib / interpreter tree."""
    if (path / 'os.py').is_file():
        return True
    if (path / 'Lib').is_dir() and (path / 'DLLs').is_dir():
        return True
    try:
        entries = list(path.iterdir())
    except OSError:
        return False
    return any(
        e.suffix == '.zip' and e.name.startswith('python') for e in entries
    )


def _is_python_install_path(path: Path) -> bool:
    """True for stdlib / venv / site-packages paths (not project sources).

    `sys.base_prefix` cannot be compared with `Path.relative_to` alone:
    uv keeps both `cpython-3.14-...` (reported by the interpreter) and
    `cpython-3.14.5-...` (present in `sys.path`) directory names, so the
    comparison is done by string prefix plus content markers.
    """
    if 'site-packages' in path.parts or 'dist-packages' in path.parts:
        return True
    for root in (
        sys.prefix,
        sys.base_prefix,
        sys.exec_prefix,
        sys.base_exec_prefix,
    ):
        if _same_or_under(path, root):
            return True
    if _looks_like_python_install(path) or _looks_like_python_install(
        path.parent
    ):
        return True
    return False


def default_folders() -> list[Path]:
    """Folders watched by default: the `sys.path` / `$PYTHONPATH` entries.

    Entries that live inside the Python installation (the stdlib, the
    active virtualenv, `site-packages`) are skipped — they are not project
    sources and would only add noise. Relative entries are resolved
    against the current working directory, which is also the base
    Streamlit itself uses for `sys.path[0]`.
    """
    candidates: list[str] = list(sys.path)
    python_path = os.environ.get('PYTHONPATH', '')
    if python_path:
        candidates.extend(python_path.split(os.pathsep))

    folders: list[Path] = []
    for entry in candidates:
        entry = entry.strip()
        if entry in ('', '.'):
            entry = os.getcwd()
        try:
            path = Path(entry).expanduser().resolve()
        except OSError:
            continue
        if not path.is_dir() or path in folders:
            continue
        if _is_python_install_path(path):
            continue
        folders.append(path)
    return folders


# ---------------------------------------------------------------------------
# watcher
# ---------------------------------------------------------------------------


def _stat_key(path: str) -> tuple[int, int] | None:
    try:
        info = os.stat(path)
    except OSError:
        return None
    return (info.st_mtime_ns, info.st_size)


class SourceWatcher:
    """Watch folders/files and report the set of changed source files.

    `on_change` is called from watchdog's observer thread with the set of
    absolute paths that changed since the previous report.
    """

    def __init__(self, on_change: tp.Callable[[set[str]], None]) -> None:
        self._on_change = on_change
        self._observer: tp.Any = None
        self._lock = threading.Lock()
        # path -> (mtime_ns, size); used to drop duplicate / spurious
        # events (a deleted file is recorded as (0, -1)).
        self._seen: dict[str, tuple[int, int]] = {}
        self._pending: set[str] = set()
        self._timer: threading.Timer | None = None
        self.folders: list[Path] = []
        self.files: list[Path] = []

    @property
    def available(self) -> bool:
        return _is_available

    def start(
        self, folders: tp.Iterable[Path], files: tp.Iterable[Path]
    ) -> bool:
        """Schedule every existing folder/file; returns True when watching."""
        if _API is None:
            return False
        observer_cls, handler_base = _API

        self.folders = [p for p in folders if p.is_dir()]
        self.files = [p for p in files if p.is_file()]
        if not self.folders and not self.files:
            return False

        handler = _make_handler(self, handler_base)
        self._observer = observer_cls()
        for folder in self.folders:
            # `str(folder)` is passed through unchanged (no `resolve()`), so
            # a symlinked folder is watched through its symlink path.
            self._observer.schedule(handler, str(folder), recursive=True)
        for file in self.files:
            self._observer.schedule(handler, str(file), recursive=False)
        self._observer.daemon = True
        self._observer.start()
        return True

    def stop(self) -> None:
        observer = self._observer
        if observer is None:
            return
        try:
            observer.stop()
            observer.join(timeout=1.0)
        except Exception:  # pragma: no cover - best effort shutdown
            pass
        self._observer = None

    # -- event handling (observer thread) --------------------------------

    def _handle(self, raw_path: str, deleted: bool) -> None:
        path = os.path.abspath(raw_path)
        if Path(path).suffix.lower() not in WATCH_SUFFIXES:
            return
        if any(part in _IGNORED_DIRS for part in Path(path).parts):
            return
        key = (0, -1) if deleted else _stat_key(path)
        if key is None:
            return
        with self._lock:
            if self._seen.get(path) == key:
                return
            self._seen[path] = key
            self._pending.add(path)
            if self._timer is None:
                self._timer = threading.Timer(_DEBOUNCE, self._flush)
                self._timer.daemon = True
                self._timer.start()

    def _flush(self) -> None:
        with self._lock:
            changed = set(self._pending)
            self._pending.clear()
            self._timer = None
        if changed:
            self._on_change(changed)


def _make_handler(watcher: SourceWatcher, base: tp.Any) -> tp.Any:
    """Build the watchdog handler bound to `watcher`."""

    def on_any_event(self: tp.Any, event: tp.Any) -> None:
        if event.event_type == 'opened' or event.is_directory:
            return
        if event.event_type == 'moved':
            # A rename shows up as two paths; report both.
            watcher._handle(event.src_path, deleted=True)
            watcher._handle(event.dest_path, deleted=False)
            return
        watcher._handle(event.src_path, deleted=event.event_type == 'deleted')

    return type('_Handler', (base,), {'on_any_event': on_any_event})()
