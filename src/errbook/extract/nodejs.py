"""Node.js / npm 提取器：JS 异常行 + `at` 栈、ERR_* 错误码、npm error 块。

Python 的裸异常行长得像 JS 异常行，所以有 `at` 栈或 ERR_ 码才认领——
这是两种不同的运行时，修法不同，不能冒领。
"""

from __future__ import annotations

import re
from typing import Iterable, Sequence, Set

from ..signature import normalize_text
from . import Claim

_EXC_RE = re.compile(
    r"^(?:Uncaught )?(?P<type>[A-Za-z_$][\w$]*(?:Error|Exception))"
    r"(?: \[(?P<code>ERR_[A-Z0-9_]+)\])?: (?P<msg>.+)$"
)
_CODE_RE = re.compile(r"^(?:[\w$.]+ )?\[(?P<code>ERR_[A-Z0-9_]+)\]: (?P<msg>.+)$")
_AT_RE = re.compile(r"^\s+at\s")
_NPM_RE = re.compile(r"^npm (?:error|ERR!) (.+)$")


def scan(lines: Sequence[str], claimed: Set[int]) -> Iterable[Claim]:
    i, n = 0, len(lines)
    while i < n:
        # npm 错误块：连续的 npm error 行（空行截断，后面的 log 路径行不带）
        if _NPM_RE.match(lines[i]):
            j = i + 1
            while j < n and _NPM_RE.match(lines[j]):
                j += 1
            yield Claim(i, j, "node", normalize_text("\n".join(lines[i:j])))
            i = max(j, i + 1)
            continue
        cm = _CODE_RE.match(lines[i])
        em = _EXC_RE.match(lines[i])
        if cm or (em and em.group("code")):
            j = i + 1
            while j < n and _AT_RE.match(lines[j]):
                j += 1
            yield Claim(i, j, "node", normalize_text(lines[i]))
            i = max(j, i + 1)
            continue
        if em:
            # 无错误码的异常行：后面跟 `at` 栈才认领（JS 运行时的形状）
            j = i + 1
            while j < n and lines[j].strip() == "":
                j += 1
            if j < n and _AT_RE.match(lines[j]):
                while j < n and _AT_RE.match(lines[j]):
                    j += 1
                yield Claim(i, j, "node", normalize_text(lines[i]))
                i = max(j, i + 1)
                continue
        i += 1
