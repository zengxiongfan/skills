"""Shared helpers for reqdoc2md."""
from __future__ import annotations

import hashlib
import json
import re
import subprocess
from pathlib import Path
from typing import Any

_INVALID = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
_RESERVED = {
    'CON', 'PRN', 'AUX', 'NUL',
    *(f'COM{i}' for i in range(1, 10)),
    *(f'LPT{i}' for i in range(1, 10)),
}


def sanitize_filename(name: str, fallback: str = '附件', max_len: int = 120) -> str:
    """Make a filesystem-safe stem while keeping Chinese characters intact."""
    name = str(name or '').strip()
    name = _INVALID.sub('_', name)
    name = name.rstrip(' .')
    if not name:
        name = fallback
    if name.upper() in _RESERVED:
        name = f'_{name}'
    if len(name) > max_len:
        name = name[:max_len].rstrip(' .')
    return name or fallback


def unique_stem(base: str, used: set[str]) -> str:
    """Return a stem that is unique inside ``used`` and register it."""
    base = sanitize_filename(base)
    name = base
    n = 2
    while name.casefold() in used:
        name = f'{base}_{n}'
        n += 1
    used.add(name.casefold())
    return name


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: str | Path) -> str:
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def ensure_dir(path: str | Path) -> Path:
    p = Path(path)
    p.mkdir(parents=True, exist_ok=True)
    return p


def write_text(path: str | Path, text: str) -> Path:
    p = Path(path)
    ensure_dir(p.parent)
    p.write_text(text, encoding='utf-8')
    return p


def write_json(path: str | Path, obj: Any, indent: int = 2) -> Path:
    return write_text(path, json.dumps(obj, ensure_ascii=False, indent=indent) + '\n')


def run_cmd(
    cmd: list[str],
    input_text: str | None = None,
    timeout: int = 600,
    cwd: str | Path | None = None,
) -> subprocess.CompletedProcess:
    """Run a command with UTF-8 decoding and a timeout."""
    return subprocess.run(
        cmd,
        input=input_text,
        capture_output=True,
        encoding='utf-8',
        errors='replace',
        timeout=timeout,
        cwd=str(cwd) if cwd else None,
    )


def relpath(path: str | Path, start: str | Path) -> str:
    """Return a POSIX-style path relative to ``start``."""
    try:
        return Path(path).resolve().relative_to(Path(start).resolve()).as_posix()
    except ValueError:
        return Path(path).as_posix()
