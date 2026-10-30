"""项目识别（任务书 2.4）：git remote 名或目录名。查询默认当前项目，--all 跨项目。"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Optional


def _git(args: list, cwd: Optional[str] = None) -> str:
    try:
        r = subprocess.run(
            ["git", *args],
            cwd=cwd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=3,
        )
        return (r.stdout or "").strip() if r.returncode == 0 else ""
    except Exception:
        return ""


def detect_project(cwd: Optional[str] = None) -> str:
    """git remote（origin 优先）的仓库名；不在仓库里就用目录名。"""
    url = _git(["remote", "get-url", "origin"], cwd)
    if not url:
        for name in _git(["remote"], cwd).splitlines():
            url = _git(["remote", "get-url", name.strip()], cwd)
            if url:
                break
    if url:
        name = url.rstrip("/").split("/")[-1]
        if name.endswith(".git"):
            name = name[: -len(".git")]
        if name:
            return name
    return Path(cwd or os.getcwd()).name


def git_head(cwd: Optional[str] = None) -> Optional[str]:
    """当前 git HEAD（solve 时可选附带；不在仓库或 git 不可用就 None）。"""
    return _git(["rev-parse", "HEAD"], cwd) or None
