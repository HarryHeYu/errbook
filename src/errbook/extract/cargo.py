"""Rust 提取器：rustc 的 error[E0xxx]: / error: 块，及 cargo 自身的 error:。

rustc 的错误块结构固定：错误行 + ``-->`` 跨度 + 代码摘录 + note，
全部缩进；归一化只取错误行（含 E 码与符号名），跨度与摘录进摘录。
"error: could not compile ... due to N previous errors" 是 cargo 的
汇总行，只占坑不记账（absorb），免得每次失败都堆一条噪音。
"""

from __future__ import annotations

import re
from typing import Iterable, Sequence, Set

from ..signature import normalize_text
from . import Claim

_ERR_RE = re.compile(r"^error(?:\[(?P<code>E\d{4,5})\])?: (?P<msg>.+)$")
_FOOTER_RE = re.compile(r"^error: could not compile .+? due to \d+ previous errors?$")


def scan(lines: Sequence[str], claimed: Set[int]) -> Iterable[Claim]:
    i, n = 0, len(lines)
    while i < n:
        m = _FOOTER_RE.match(lines[i])
        if m:
            j = i + 1
            while j < n and lines[j].startswith((" ", "\t")):
                j += 1
            yield Claim(i, j, "cargo", None, absorb=True)
            i = max(j, i + 1)
            continue
        m = _ERR_RE.match(lines[i])
        if m:
            j = i + 1
            while j < n:
                ln = lines[j]
                if ln.startswith((" ", "\t")):
                    j += 1
                    continue
                if ln == "" and j + 1 < n and lines[j + 1].startswith((" ", "\t")):
                    j += 1
                    continue
                break
            yield Claim(i, j, "cargo", normalize_text(lines[i]))
            i = max(j, i + 1)
            continue
        i += 1
