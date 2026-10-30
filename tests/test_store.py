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
    long_text = "\n".join(f"line {i}" for i in range(100)) + "\nkey sk-abc123def456ghi789"
    res = store.record([Extraction("generic", long_text, "boom", False)], project="p")
    occ = store.occurrences_for(res[0]["sig_id"])[0]
    assert "省略" in occ["excerpt"]
    assert "sk-abc123def456ghi789" not in occ["excerpt"]
    assert "[masked]" in occ["excerpt"]


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
