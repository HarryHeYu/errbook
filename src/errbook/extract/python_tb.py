"""Python 提取器：标准 traceback（含链式异常、3.11+ 精细定位）与 pytest 的 E 行。

签名取最后一个异常块——链式异常里真正抛出的是最后一个。
归一化只保留 异常类型 + 消息骨架，不保留 frame 的文件与行号：
同一个坑换个文件撞，还是同一个坑。
"""

from __future__ import annotations

import re
from typing import Iterable, Sequence, Set

from ..signature import normalize_text
from . import Claim

_TB_RE = re.compile(r"^Traceback \(most recent call last\):")
_CHAIN_RE = re.compile(
    r"^(?:During handling of the above exception"
    r"|The above exception was the direct cause of the following exception)"
)
# 异常行：类型以 Error/Exception/… 结尾，或那几个不以 Error 结尾的内建异常
_EXC_LINE_RE = re.compile(
    r"^(?P<type>[A-Za-z_][\w.]*(?:Error|Exception|Exit|Interrupt|Warning"
    r"|StopIteration|GeneratorExit))(?::\s?(?P<msg>.*))?$"
)
# 兜底：非空消息的 "Xxx: msg" 也当异常收（自定义异常类不一定叫 XxxError）
_EXC_LOOSE_RE = re.compile(r"^[A-Za-z_][\w.]*:\s+\S.*$")
_PYTEST_RE = re.compile(
    r"^E\s+(?P<type>[A-Za-z_][\w.]*(?:Error|Exception|Exit|Interrupt|Warning))"
    r"(?::\s?(?P<msg>.*))?$"
)
# 无 traceback 头的裸异常块（SyntaxError / 模块级语法错误）：
# "  File \"x.py\", line N" 开头的缩进 File 行
_FILE_LINE_RE = re.compile(r'^\s+File "(?P<file>[^"]+)", line (?P<line>\d+)')


def _norm_exc(type_: str, msg: str | None) -> str:
    msg = (msg or "").strip()
    return normalize_text(f"{type_}: {msg}" if msg else type_)


def scan(lines: Sequence[str], claimed: Set[int]) -> Iterable[Claim]:
    local_done: set[int] = set()  # 本提取器内部的去重
    i, n = 0, len(lines)
    while i < n:
        if i not in local_done and _TB_RE.match(lines[i]):
            # 块尾：第一个非空且不缩进的行就是异常行
            j = i + 1
            while j < n and (lines[j] == "" or lines[j].startswith((" ", "\t"))):
                j += 1
            # 链式异常：异常行之后（隔空行）是 "During handling..." 标记，
            # 说明还有下一段 traceback——真正抛出的是最后一段，跳过去
            k = j + 1
            while k < n and lines[k] == "":
                k += 1
            if k < n and _CHAIN_RE.match(lines[k]):
                i = k + 1
                continue
            exc_line = lines[j] if j < n else ""
            norm = None
            em = _EXC_LINE_RE.match(exc_line)
            if em:
                norm = _norm_exc(em.group("type"), em.group("msg"))
            elif _EXC_LOOSE_RE.match(exc_line):
                norm = normalize_text(exc_line)
            end = min(j + 1, n)
            yield Claim(i, end, "python-traceback", norm, fuzzy=norm is None)
            local_done.update(range(i, end))
            i = max(end, i + 1)
            continue
        if i not in local_done and _FILE_LINE_RE.match(lines[i]):
            # 裸语法错误块：File 行之后几行内出现列 0 的异常行
            j = i + 1
            exc_idx = None
            while j < n and j <= i + 8:
                ln = lines[j]
                if ln == "" or ln.startswith((" ", "\t")):
                    j += 1
                    continue
                em = _EXC_LINE_RE.match(ln)
                if em:
                    exc_idx = j
                break  # 第一个列 0 非空行：是异常行就收，不是就结束
            if exc_idx is not None:
                em = _EXC_LINE_RE.match(lines[exc_idx])
                end = min(exc_idx + 1, n)
                yield Claim(
                    i, end, "python-traceback", _norm_exc(em.group("type"), em.group("msg"))
                )
                local_done.update(range(i, end))
                i = end
                continue
        pm = _PYTEST_RE.match(lines[i])
        if pm:
            j = i + 1
            while j < n and _PYTEST_RE.match(lines[j]):
                j += 1
            yield Claim(
                i, j, "python-traceback", _norm_exc(pm.group("type"), pm.group("msg"))
            )
            i = j
            continue
        i += 1
