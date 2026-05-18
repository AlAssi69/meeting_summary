#!/usr/bin/env python3
"""Pre-GitHub checks: sensitive paths tracked by git (requires .git + git on PATH).

Also scans tracked text files under src/, tests/, docs/, and main.py for obvious
HF/OpenAI-style token literals (heuristic).
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# Heuristic: long hf_ or sk- style tokens (not test placeholders like hf_testtoken123).
_TOKEN_LIKE = re.compile(r"\b(hf_[A-Za-z0-9]{30,}|sk-[A-Za-z0-9]{30,})\b")

_TRACKED_SUFFIXES = (".db", ".sqlite", ".sqlite3")

# Local tool / package caches — must not be published (see .gitignore).
_CACHE_DIR_NAMES = frozenset(
    {
        ".mypy_cache",
        ".ruff_cache",
        ".tox",
        ".nox",
        ".hypothesis",
        ".cache",
        ".uv",
        "__pypackages__",
        ".pytest_cache",
        "htmlcov",
    }
)


def _git_ls_files() -> list[str] | None:
    if not (ROOT / ".git").is_dir():
        return None
    try:
        r = subprocess.run(
            ["git", "-C", str(ROOT), "ls-files", "-z"],
            capture_output=True,
            check=False,
        )
    except FileNotFoundError:
        print("audit_repo_before_github: 'git' executable not found on PATH.")
        return None
    if r.returncode != 0:
        err = (r.stderr or b"").decode("utf-8", errors="replace").strip()
        print(f"audit_repo_before_github: git ls-files failed ({r.returncode}): {err}")
        return None
    raw = (r.stdout or b"").decode("utf-8", errors="replace")
    if not raw:
        return []
    return [p for p in raw.split("\0") if p]


def _sensitive_tracked(paths: list[str]) -> list[str]:
    bad: list[str] = []
    for p in paths:
        pl = p.replace("\\", "/")
        if pl == ".env" or pl.startswith(".env/"):
            bad.append(p)
            continue
        if pl.startswith("meeting_outputs/") or pl == "meetings.db":
            bad.append(p)
            continue
        if pl.startswith("models/whisper/"):
            bad.append(p)
            continue
        if any(part in _CACHE_DIR_NAMES for part in pl.split("/")):
            bad.append(p)
            continue
        base = Path(pl).name
        if base == "meetings.db" or pl.endswith(_TRACKED_SUFFIXES):
            bad.append(p)
    return sorted(set(bad))


def _scan_source_literals() -> list[tuple[str, str]]:
    hits: list[tuple[str, str]] = []
    globs = ["src/**/*.py", "tests/**/*.py", "docs/**/*.md", "main.py"]
    for pattern in globs:
        for path in ROOT.glob(pattern):
            if ".venv" in path.parts:
                continue
            try:
                text = path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            for m in _TOKEN_LIKE.finditer(text):
                rel = path.relative_to(ROOT).as_posix()
                hits.append((rel, m.group(1)[:20] + "…"))
    return hits


def main() -> int:
    paths = _git_ls_files()
    if paths is None:
        if not (ROOT / ".git").is_dir():
            print("audit_repo_before_github: no .git at repo root - skipped git index check.")
            print("  After git init / clone, run: python scripts/audit_repo_before_github.py")
        exit_code = 0
    else:
        flagged = _sensitive_tracked(paths)
        if flagged:
            print("audit_repo_before_github: tracked paths that should NOT be public:")
            for p in flagged:
                print(f"  - {p}")
            print("  Fix: git rm -r --cached <paths> then commit; ensure .gitignore covers them.")
            exit_code = 1
        else:
            print("audit_repo_before_github: no sensitive paths in git index (env, DB, outputs, whisper cache, tool caches).")
            exit_code = 0

    src_hits = _scan_source_literals()
    if src_hits:
        print("audit_repo_before_github: possible token-like literals in tracked areas:")
        for rel, preview in src_hits:
            print(f"  - {rel}: {preview}")
        exit_code = 1
    else:
        print("audit_repo_before_github: no hf_/sk- long literals under src/, tests/, docs/, main.py.")

    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
