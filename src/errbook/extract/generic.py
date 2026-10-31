"""generic 兜底（任务书 2.2）：未被认领的错误行 + 多行重复模式去噪。

两种把握度：
- 行首（允许时间戳/级别标签前缀）就是 error/fatal/failed/panic 字样
  → 归一化有把握，fuzzy=False；
- 连续重复 ≥3 次的相同行（刷屏噪声）→ 只存原文，fuzzy=True。
"""

from __future__ import annotations

import re
from typing import Iterable, Sequence, Set

from ..signature import normalize_text
from . import Claim

_ERRISH_RE = re.compile(
    r"^\s*"
    r"(?:\[[^\]]{1,30}\]\s*)?"  # 可选 [时间戳/级别] 标签
    r"(?:[\w@+.-]{1,24}:\s*)?"  # 可选 "make:" / "collect2:" 前缀
    r"(?:ERROR|Error|error|FATAL|Fatal|fatal|FAILED|Failed|failed"
    r"|PANIC|Panic|panic|Exception)\b:?"
)
_MAKE_RE = re.compile(r"^\s*make(?:\[\d+\])?:\s*\*\*\*")
# 裸异常行（XxxError: / XxxException:，无 traceback 头、无 at 栈）。
# python-traceback 已在前面认领了带头的块，node 认领了带 at 栈的；
# 走到这里还没人认领的裸异常行归 generic（java/python/各类运行时通用）。
_EXC_LINE_RE = re.compile(r"^[A-Za-z_][\w.]*(?:Error|Exception):\s*\S")


def scan(lines: Sequence[str], claimed: Set[int]) -> Iterable[Claim]:
    i, n = 0, len(lines)
    while i < n:
        if i in claimed:
            i += 1
            continue
        if (
            _ERRISH_RE.match(lines[i])
            or _MAKE_RE.match(lines[i])
            or _EXC_LINE_RE.match(lines[i])
        ):
            yield Claim(i, i + 1, "generic", normalize_text(lines[i]))
            i += 1
            continue
        if (
            lines[i].strip()
            and i + 2 < n
            and lines[i] == lines[i + 1] == lines[i + 2]
            and all(k not in claimed for k in (i, i + 1, i + 2))
        ):
            j = i
            while j < n and lines[j] == lines[i] and j not in claimed:
                j += 1
            yield Claim(i, j, "generic", None, fuzzy=True)
            i = j
            continue
        i += 1
