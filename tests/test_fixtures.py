"""归一化测试矩阵（任务书 M2）：每个提取器 ≥5 个真实样本 + 跨版本/跨环境变体。"""

import json
from pathlib import Path

import pytest

from errbook.extract import extract_all

FIXTURES = Path(__file__).parent / "fixtures"
INDEX = json.loads((FIXTURES / "index.json").read_text(encoding="utf-8"))


def _exts(rel: str):
    text = (FIXTURES / rel).read_text(encoding="utf-8")
    return extract_all(text)


def _describe(exts):
    return [(e.tool, e.fuzzy, e.normalized[:70]) for e in exts]


@pytest.mark.parametrize(
    "sample", INDEX["samples"], ids=[s["file"] for s in INDEX["samples"]]
)
def test_sample(sample):
    exts = _exts(sample["file"])
    if sample["tool"] is None:
        assert len(exts) == 0, _describe(exts)
        return
    assert len(exts) >= sample["min_errors"], _describe(exts)
    matching = [e for e in exts if e.tool == sample["tool"]]
    assert matching, f"工具 {sample['tool']} 没认领；实际：{_describe(exts)}"
    if "fuzzy" in sample:
        assert any(e.fuzzy == sample["fuzzy"] for e in matching), _describe(exts)
    for absent in sample.get("absent_tools", []):
        assert all(e.tool != absent for e in exts), f"{absent} 不该认领：{_describe(exts)}"


@pytest.mark.parametrize(
    "group",
    INDEX["same_signature_groups"],
    ids=[g[0] for g in INDEX["same_signature_groups"]],
)
def test_same_signature(group):
    norms = []
    for rel in group:
        exts = _exts(rel)
        assert exts, f"{rel} 没有提取结果"
        norms.append(exts[0].normalized)
    assert len(set(norms)) == 1, f"变体签名不一致：\n" + "\n".join(norms)
