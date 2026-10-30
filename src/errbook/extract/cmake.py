"""CMake 提取器：``CMake Error at <file>:<line> (<cmd>):`` 块与不带头的 CMake Error。"""

from __future__ import annotations

import re
from typing import Iterable, Sequence, Set

from ..signature import normalize_text
from . import Claim

_AT_RE = re.compile(r"^CMake Error at .+?:\d+(?:,\d+)? \([^)]*\):")
_PLAIN_RE = re.compile(
    r"^CMake Error\b|^CMake Generate Step failed|^CMake Build Error"
)


def scan(lines: Sequence[str], claimed: Set[int]) -> Iterable[Claim]:
    i, n = 0, len(lines)
    while i < n:
        if _AT_RE.match(lines[i]) or _PLAIN_RE.match(lines[i]):
            j = i + 1
            while j < n:
                ln = lines[j]
                if ln.startswith((" ", "\t")):
                    j += 1
                    continue
                # 空行只有在后面还跟缩进行时才算块内
                if ln == "" and j + 1 < n and lines[j + 1].startswith((" ", "\t")):
                    j += 1
                    continue
                break
            yield Claim(i, j, "cmake", normalize_text("\n".join(lines[i:j])))
            i = max(j, i + 1)
        else:
            i += 1
