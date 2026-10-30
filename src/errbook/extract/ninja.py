"""Ninja 提取器：``FAILED:`` 块与 ``ninja: error:`` 行。

ninja 只是包装器——FAILED 块里更具体的错误（gcc/msvc/python…）会先被
其他提取器认领，此时 ninja 整块让路；块里没有任何已知错误时 ninja
兜底认领，并如实标 fuzzy（同一条命令反复失败才值得记，归一化没把握）。
"""

from __future__ import annotations

import re
from typing import Iterable, Sequence, Set

from ..signature import normalize_text
from . import Claim

_FAILED_RE = re.compile(r"^FAILED: ?(.*)")
_ERR_RE = re.compile(r"^ninja: error: (.+)$")
_STOP_RE = re.compile(r"^ninja: build stopped")


def scan(lines: Sequence[str], claimed: Set[int]) -> Iterable[Claim]:
    i, n = 0, len(lines)
    while i < n:
        m = _FAILED_RE.match(lines[i])
        if m:
            j = i + 1
            while j < n and not _FAILED_RE.match(lines[j]) and not _STOP_RE.match(lines[j]):
                j += 1
            if any(k in claimed for k in range(i, j)):
                # 块里的具体错误已被别的工具认领，ninja 不重复记账
                i = j
                continue
            yield Claim(i, j, "ninja", None, fuzzy=True)
            i = max(j, i + 1)
            continue
        if _ERR_RE.match(lines[i]):
            yield Claim(i, i + 1, "ninja", normalize_text(lines[i]))
            i += 1
            continue
        i += 1
