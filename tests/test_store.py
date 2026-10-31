import pytest

from errbook.signature import Extraction
from errbook.store import AmbiguousSig, SigNotFound


def make_ext(
    tool="cmake",
    normalized="CMake Error at <path>:<N> (find_package): By not providing 'Foo'",
    excerpt='CMake Error at CMakeLists.txt:5 (find_package):\n  By not providing "FindFoo.cmake"',
    fuzzy=False,
):
    return Extraction(tool=tool, excerpt=excerpt, normalized=normalized, fuzzy=fuzzy)


def test_record_dedup_within_capture(store):
    res = store.record([make_ext()] * 3, project="demo")
    assert len(res) == 1
    assert res[0]["new"] is True
    assert res[0]["count"] == 1


def test_count_grows_across_captures(store):
    store.record([make_ext()], project="demo")
    res = store.record([make_ext()], project="demo")
    assert res[0]["new"] is False
    assert res[0]["count"] == 2


def test_hit_requires_fix_or_count_two(store):
    exts = [make_ext()]
    store.record(exts, project="demo")
    # 出现 1 次又没修法 → 不打扰
    assert store.find_hits(exts, project="demo") == []
    store.record(exts, project="demo")
    # 出现 ≥2 次没修法 → 提醒补记录
    hits = store.find_hits(exts, project="demo")
    assert len(hits) == 1 and hits[0]["fixes"] == []
    store.add_fix(hits[0]["sig"]["id"], "装了 Foo 开发包")
    # 有修法 → 提醒并带出修法
    hits = store.find_hits(exts, project="demo")
    assert hits[0]["fixes"][0]["note"] == "装了 Foo 开发包"


def test_project_scoping(store):
    exts = [make_ext()]
    store.record(exts, project="alpha")
    store.add_fix(store.find_by_prefix("")[0]["id"], "x")
    assert store.find_hits(exts, project="beta") == []
    assert store.find_hits(exts, project="alpha")
    assert store.find_hits(exts, project=None)  # --all 跨项目


def test_fuzzy_hidden_by_default(store):
    exts = [make_ext(tool="generic", normalized="weird output", fuzzy=True)]
    store.record(exts, project="demo")
    store.record(exts, project="demo")
    assert store.find_hits(exts, project="demo") == []
    assert store.find_hits(exts, project="demo", include_fuzzy=True)


def test_excerpt_truncated_and_masked(store):
    # 走 extract_all 全链路：脱敏在源头单点完成，入库摘录必须已打码
    from errbook.extract import extract_all

    body = (
        "Traceback (most recent call last):\n"
        '  File "svc.py", line 9, in main\n'
        "    login(key=\"sk-proj1234567890abcdef\", digest=d41d8cd98f00b204e9800998ecf8427e)\n"
        "ValueError: auth rejected\n"
    )
    exts = extract_all(body)
    res = store.record(exts, project="p")
    occ = store.occurrences_for(res[0]["sig_id"])[0]
    assert "sk-proj1234567890abcdef" not in occ["excerpt"]
    assert "d41d8cd98f00b204e9800998ecf8427e" not in occ["excerpt"]
    assert "[masked]" in occ["excerpt"]


def test_redact_symmetric_between_record_and_find_hits(store):
    """P1 回归钉：含密钥的错误第二次出现必须能命中（签名输入两侧一致）。

    密钥必须在归一化签名行里，否则两侧哈希天然一致，测不出不对称。
    """
    from errbook.extract import extract_all

    body = "ValueError: auth rejected for token Bearer abcdefgh12345678\n"
    exts = extract_all(body)
    assert "[masked]" in exts[0].normalized  # 源头已脱敏
    store.record(exts, project="p")
    store.record(exts, project="p")  # 第二次出现
    hits = store.find_hits(exts, project="p")
    assert len(hits) == 1  # count≥2 无修法 → 提醒；若签名输入不对称这里会是 0


def test_search_finds_fix_note_with_short_cjk_query(store):
    res = store.record([make_ext()], project="demo")
    store.add_fix(res[0]["sig_id"], "把配置拷贝到发布目录并重启服务")
    # 2 字中文走 LIKE 兜底，兜底必须覆盖修法（fixes.note）
    rows = store.search("发布", project="demo")
    assert len(rows) == 1


def test_search_by_excerpt_and_fix(store):
    res = store.record([make_ext()], project="demo")
    store.add_fix(res[0]["sig_id"], "重装了 GTest 并且加了 REQUIRED")
    rows = store.search("GTest", project="demo")
    assert len(rows) == 1
    assert rows[0]["id"] == res[0]["sig_id"]


def test_search_short_query_fallback(store):
    store.record([make_ext()], project="demo")
    rows = store.search("Foo", project="demo")
    assert len(rows) == 1


def test_forget_removes_everything(store):
    res = store.record([make_ext()], project="demo")
    store.add_fix(res[0]["sig_id"], "fixed")
    sig = store.forget(res[0]["sig_id"][:4])
    assert sig["id"] == res[0]["sig_id"]
    assert store.find_hits([make_ext()], project="demo") == []
    assert store.search("FindFoo", project=None) == []


def test_resolve_prefix(store):
    res = store.record([make_ext()], project="demo")
    sig = store.resolve_sig(res[0]["sig_id"][:6])
    assert sig["id"] == res[0]["sig_id"]
    with pytest.raises(SigNotFound):
        store.resolve_sig("ffffffffffff")
    with pytest.raises(SigNotFound):
        store.resolve_sig("%%")  # 剥掉通配符后为空 → 拒绝，不许全表列出


def test_hit_count_is_project_scoped(store):
    """同签名在 A、B 各出现一次：在 A 的视角这仍是第一次，不该提醒。"""
    exts = [make_ext()]
    store.record(exts, project="alpha")
    store.record(exts, project="beta")
    assert store.find_hits(exts, project="alpha") == []
    assert store.find_hits(exts, project=None)  # --all 视角全局 count=2


def test_fts_disabled_falls_back_to_like(store):
    """无 FTS5 的环境（Windows 官方 CPython ≤3.10）必须能降级工作。"""
    store.fts_tokenizer = None
    res = store.record([make_ext()], project="demo")
    assert res[0]["sig_id"]
    rows = store.search("FindFoo", project="demo")  # LIKE 兜底仍能搜到
    assert len(rows) == 1
    # 记录与删除不因缺 FTS 而崩
    store.add_fix(res[0]["sig_id"], "ok")
    assert store.forget(res[0]["sig_id"][:4])["id"] == res[0]["sig_id"]
