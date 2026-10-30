"""GCC / Clang 提取器：``file:line[:col]: error:`` 诊断行（clang 的 note 行
与代码摘录一并认领），以及 ld / lld 的 undefined reference / undefined symbol。

归一化只取诊断行本身——同一条 error 在别的上下文出现（不同代码摘录）
仍是同一个签名。
"""

from __future__ import annotations

import re
from typing import Iterable, Sequence, Set

from ..signature import normalize_text
from . import Claim

_DIAG_RE = re.compile(
    r"^(?P<path>(?:[A-Za-z]:)?[^:]+):(?P<line>\d+)(?::\d+)?: "
    r"(?P<sev>fatal error|error|note|warning): (?P<msg>.*)$"
)
_LD_RE = re.compile(r"\bundefined reference to\b|\bundefined symbol: ")
_COLLECT2_RE = re.compile(r"^collect2: error: ld returned \d+ exit status$")


def scan(lines: Sequence[str], claimed: Set[int]) -> Iterable[Claim]:
    i, n = 0, len(lines)
    while i < n:
        m = _DIAG_RE.match(lines[i])
        if m and m.group("sev") in ("fatal error", "error"):
            j = i + 1
            while j < n:
                ln = lines[j]
                if ln.startswith((" ", "\t")):  # 代码摘录 / 插入符
                    j += 1
                    continue
                nm = _DIAG_RE.match(ln)
                if nm and nm.group("sev") in ("note", "warning"):
                    j += 1
                    continue
                break
            yield Claim(i, j, "gcc-clang", normalize_text(lines[i]))
            i = max(j, i + 1)
            continue
        if _LD_RE.search(lines[i]):
            yield Claim(i, i + 1, "gcc-clang", normalize_text(lines[i]))
            i += 1
            continue
        if _COLLECT2_RE.match(lines[i]):
            # 链接失败汇总行，符号级信息在上面，占坑防噪音
            yield Claim(i, i + 1, "gcc-clang", None, absorb=True)
            i += 1
            continue
        i += 1
