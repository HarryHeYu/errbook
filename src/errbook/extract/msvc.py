"""MSVC 提取器：cl.exe 编译错误（error Cxxxx / fatal error Cxxxx）、
链接错误（LNKxxxx）与 cl 命令行错误（Dxxxx）。warning 不记账。"""

from __future__ import annotations

import re
from typing import Iterable, Sequence, Set

from ..signature import normalize_text
from . import Claim

# main.cpp(12): error C2065: ...   /   1>main.cpp(12,5): error C2065: ...
_MSVC_RE = re.compile(
    r"^\s*(?:\d+>)?.*?"
    r"\(\d+(?:,\d+)?\):\s*(?:fatal error|error)\s+([A-Z]\d{4,6})\s*:\s*(.+)$"
)
# foo.obj : error LNK2019: ... / LNK1104
_LNK_RE = re.compile(
    r"^\s*(?:\d+>)?.*?\b(?:fatal error|error)\s+(LNK\d{4,6})\s*:\s*(.+)$"
)
# cl : Command line error D8016: ...
_CL_RE = re.compile(
    r"^\s*(?:\d+>)?\s*cl\s*:\s*(?:fatal error|error)\s+([A-Z]\d{4,6})\s*:\s*(.+)$"
)


def scan(lines: Sequence[str], claimed: Set[int]) -> Iterable[Claim]:
    i, n = 0, len(lines)
    while i < n:
        if (
            _MSVC_RE.match(lines[i])
            or _LNK_RE.match(lines[i])
            or _CL_RE.match(lines[i])
        ):
            j = i + 1
            # 缩进的续行（模板诊断的展开等）一并算进摘录
            while j < n and lines[j].startswith((" ", "\t")):
                j += 1
            yield Claim(i, j, "msvc", normalize_text("\n".join(lines[i:j])))
            i = max(j, i + 1)
        else:
            i += 1
