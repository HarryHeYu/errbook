"""提取器注册表（任务书 2.2）。

每种工具一个提取器；注册顺序即认领优先级——越具体的越先认领，
后面的提取器跳过已被认领的行，同一段错误不会被两个工具重复记账。
归一化结果给不出来就交 None，注册表兜底存原文并如实标 fuzzy。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Iterable, Optional, Sequence, Set

from ..redact import redact
from ..signature import Extraction, normalize_text

# 单次采集最多入库多少条错误，防日志爆炸
MAX_ERRORS_PER_TEXT = 50


@dataclass
class Claim:
    """一个提取器对一段行的认领。"""

    start: int  # 起始行（含）
    end: int  # 结束行（不含）
    tool: str
    normalized: Optional[str]  # None → 用摘录兜底并标 fuzzy
    fuzzy: bool = False
    absorb: bool = False  # True = 只占坑不记账（无信息量的汇总行）


Scanner = Callable[[Sequence[str], Set[int]], Iterable[Claim]]

from . import cargo, cmake, cuda, gcc, generic, msvc, ninja, nodejs, python_tb  # noqa: E402

# 顺序即优先级：越具体的越先认领。cuda-oom 在 python-traceback 之前，
# 因为 torch 的 OOM traceback 里真正值得记账的是显存那一行。
_EXTRACTORS: list[tuple[str, Scanner]] = [
    ("cuda-oom", cuda.scan),
    ("cmake", cmake.scan),
    ("msvc", msvc.scan),
    ("gcc-clang", gcc.scan),
    ("cargo", cargo.scan),
    ("node", nodejs.scan),
    ("python-traceback", python_tb.scan),
    ("ninja", ninja.scan),
    ("generic", generic.scan),
]

TOOLS = [name for name, _ in _EXTRACTORS]


def _overlaps(start: int, end: int, claimed: list[tuple[int, int]]) -> bool:
    return any(start < e and s < end for s, e in claimed)


def extract_all(text: str) -> list[Extraction]:
    """全文过一遍注册表，产出互不重叠的错误提取结果。"""
    lines = text.splitlines()
    claimed_ranges: list[tuple[int, int]] = []
    claims: list[Claim] = []
    for _, scanner in _EXTRACTORS:
        claimed: set[int] = set()
        for s, e in claimed_ranges:
            claimed.update(range(s, e))
        for c in scanner(lines, claimed):
            if c.start >= c.end:
                continue
            if _overlaps(c.start, c.end, claimed_ranges):
                continue
            claimed_ranges.append((c.start, c.end))
            if c.absorb:
                continue  # 只占坑不记账
            claims.append(c)
    claims.sort(key=lambda c: (c.start, c.end))

    out: list[Extraction] = []
    for c in claims:
        excerpt = "\n".join(lines[c.start : c.end]).strip("\n")
        if not excerpt.strip():
            continue
        # 脱敏在源头单点完成：入库、查询、展示共用同一份文本，
        # 保证 record/find_hits 的签名输入必然一致（记了就能查中）。
        excerpt = redact(excerpt)
        if c.normalized is None:
            out.append(
                Extraction(
                    tool=c.tool,
                    excerpt=excerpt,
                    normalized=redact(normalize_text(excerpt)),
                    fuzzy=True,
                )
            )
        else:
            out.append(
                Extraction(
                    tool=c.tool, excerpt=excerpt, normalized=redact(c.normalized), fuzzy=c.fuzzy
                )
            )
        if len(out) >= MAX_ERRORS_PER_TEXT:
            break
    return out
