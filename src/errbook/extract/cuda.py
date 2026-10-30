"""CUDA OOM 提取器：显存不够是最经典的"同一个坑"，值得单独一个签名类别。

认领 OOM 消息及其显存报告（直到空行或链式异常标记）。torch 的 OOM
traceback 会同时匹配 python-traceback——本提取器排在前面优先认领，
因为"怎么省显存"和"怎么修代码"是两种修法。
"""

from __future__ import annotations

import re
from typing import Iterable, Sequence, Set

from ..signature import normalize_text
from . import Claim

_OOM_RE = re.compile(
    r"torch\.cuda\.OutOfMemoryError"
    r"|CUDA out of memory"
    r"|CUDA error: out of memory"
    r"|CUDA_ERROR_OUT_OF_MEMORY"
    r"|OOM when allocating"  # tensorflow 风格
    r"|out of memory.{0,40}\bCUDA\b",
    re.IGNORECASE,
)
_STOP_RE = re.compile(
    r"^(?:During handling of the above exception"
    r"|The above exception was the direct cause"
    r"|Traceback \(most recent call last\))"
)


def scan(lines: Sequence[str], claimed: Set[int]) -> Iterable[Claim]:
    i, n = 0, len(lines)
    while i < n:
        if _OOM_RE.search(lines[i]):
            j = i + 1
            while j < n and lines[j].strip() and not _STOP_RE.match(lines[j]):
                j += 1
            yield Claim(i, j, "cuda-oom", normalize_text("\n".join(lines[i:j])))
            i = max(j, i + 1)
        else:
            i += 1
