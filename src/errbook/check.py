"""check：stdin/file → 命中提醒（任务书 2.3）。

退出码恒为 0——它是信息附加器，不是质量门禁。
提醒条件：有 solve 记录的签名（主），或 count≥2 但还没 solve（提示补记录）；
fuzzy 签名默认不出，``--fuzzy`` 才看——不假装匹配得准。
命中展示时原文（本次摘录）与历史修法并排，由人确认是否同款。
"""

from __future__ import annotations

from typing import Optional

from .extract import extract_all
from .store import Store, fmt_ts
from .trunc import truncate_excerpt

CHECK_EXCERPT_HEAD = 6
CHECK_EXCERPT_TAIL = 3


def check_text(
    store: Store,
    text: str,
    project: Optional[str] = None,
    include_fuzzy: bool = False,
    extractions=None,
) -> tuple[str, list]:
    """对一段文本做命中检查，返回（提醒块文本, 命中列表）。"""
    if extractions is None:
        extractions = extract_all(text)
    hits = store.find_hits(extractions, project=project, include_fuzzy=include_fuzzy)
    blocks = [render_hit(h) for h in hits]
    return "\n".join(blocks), hits


def render_hit(hit: dict) -> str:
    sig = hit["sig"]
    fixes = hit["fixes"]
    ext = hit["extraction"]
    lines: list[str] = []
    head = (
        f"sig {sig['id']} · {sig['tool']} · 历史出现 {sig['count']} 次"
        f"（首次 {fmt_ts(sig['first_seen'])}）"
    )
    if fixes:
        lines.append("━━━━━━ errbook · 这错你修过 ━━━━━━")
        lines.append(head)
        lines.append("上次怎么好的：")
        for i, fx in enumerate(fixes, 1):
            git = f" · git:{fx['git_head'][:7]}" if fx["git_head"] else ""
            lines.append(f"  {i}. [{fmt_ts(fx['ts'])}{git}] {fx['note']}")
    else:
        lines.append("━━━━━━ errbook · 这错见过但没记过修法 ━━━━━━━")
        lines.append(head)
        lines.append(f'修好后请运行：errbook solve {sig["id"]} "怎么好的"')
    lines.append("本次摘录：")
    excerpt = truncate_excerpt(ext.excerpt, CHECK_EXCERPT_HEAD, CHECK_EXCERPT_TAIL)
    for ln in excerpt.splitlines():
        lines.append(f"  | {ln}")
    lines.append("━" * 44)
    return "\n".join(lines)
