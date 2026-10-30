"""摘录截断（任务书 2.4）：首尾各 N 行，中间打标记。原文永不改内容，只裁长度。"""

from __future__ import annotations

HEAD_LINES = 20
TAIL_LINES = 20


def truncate_excerpt(text: str, head: int = HEAD_LINES, tail: int = TAIL_LINES) -> str:
    lines = text.splitlines()
    if len(lines) <= head + tail + 1:
        return text
    omitted = len(lines) - head - tail
    return "\n".join(lines[:head] + [f"…（省略 {omitted} 行）…"] + lines[-tail:])
