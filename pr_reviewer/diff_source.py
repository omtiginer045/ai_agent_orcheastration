"""Where the diff under review comes from: git refs, a patch file, or stdin."""

from __future__ import annotations

import asyncio
import re
import sys
from dataclasses import dataclass
from pathlib import Path

_FILE_HEADER = re.compile(r"^diff --git a/(.+?) b/(.+)$", re.MULTILINE)


class DiffError(RuntimeError):
    pass


@dataclass(frozen=True)
class Diff:
    text: str
    repo_path: Path  # agents may Read/Grep files under here for context

    @property
    def files(self) -> list[str]:
        """Paths touched by the diff (post-change names)."""
        return [m.group(2) for m in _FILE_HEADER.finditer(self.text)]

    @property
    def is_empty(self) -> bool:
        return not self.text.strip()


async def from_git(repo_path: str | Path, base: str, head: str = "HEAD") -> Diff:
    """``git diff base...head`` — changes on head since it branched from base."""
    repo = Path(repo_path).resolve()
    proc = await asyncio.create_subprocess_exec(
        "git", "-C", str(repo), "diff", "--no-color", f"{base}...{head}",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    out, err = await proc.communicate()
    if proc.returncode != 0:
        raise DiffError(f"git diff failed: {err.decode(errors='replace').strip()}")
    return Diff(text=out.decode(errors="replace"), repo_path=repo)


def from_file(path: str | Path, repo_path: str | Path = ".") -> Diff:
    return Diff(text=Path(path).read_text(errors="replace"), repo_path=Path(repo_path).resolve())


def from_stdin(repo_path: str | Path = ".") -> Diff:
    return Diff(text=sys.stdin.read(), repo_path=Path(repo_path).resolve())
