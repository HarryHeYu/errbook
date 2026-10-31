import os

from errbook import __version__
import re
import sys

from errbook.cli import app

from .conftest import all_out
from .samples import CMAKE_ERR


def invoke(*args, **kw):
    from typer.testing import CliRunner

    return CliRunner().invoke(app, list(args), **kw)


def test_version():
    r = invoke("--version")
    assert r.exit_code == 0
    assert __version__ in r.output


def test_run_passthrough_exit_code(store_env):
    r = invoke("run", "--", sys.executable, "-c", "print('hello'); raise SystemExit(7)")
    assert r.exit_code == 7
    assert "hello" in all_out(r)


def test_run_records_then_second_run_reminds(store_env):
    script = "raise ValueError('boom boom')"
    r1 = invoke("run", "--", sys.executable, "-c", script)
    assert r1.exit_code == 1
    out1 = all_out(r1)
    assert "已入库" in out1
    assert re.search(r"\+ sig [0-9a-f]{12}", out1)  # sig-id 直接可取，solve 入口不断
    # 第二次撞同一个坑：count≥2，提醒出现
    r2 = invoke("run", "--", sys.executable, "-c", script)
    assert r2.exit_code == 1
    out2 = all_out(r2)
    assert "见过但没记过修法" in out2
    assert re.search(r"= sig [0-9a-f]{12}", out2)


def test_add_solve_check_flow(store_env, tmp_path):
    log = tmp_path / "err.log"
    log.write_text(CMAKE_ERR, encoding="utf-8")

    r1 = invoke("add", "--file", str(log))
    assert r1.exit_code == 0
    m = re.search(r"sig ([0-9a-f]{12})", all_out(r1))
    assert m, all_out(r1)
    sig = m.group(1)

    r2 = invoke("solve", sig, "装 GTest 并在 CMakeLists 加 find_package(GTest REQUIRED)")
    assert r2.exit_code == 0
    assert "已记录修法" in all_out(r2)

    r3 = invoke("check", "--file", str(log))
    assert r3.exit_code == 0  # check 恒为 0
    out = all_out(r3)
    assert "这错你修过" in out
    assert "装 GTest" in out
    assert "CMake Error" in out  # 原文摘录并排展示

    # 未命中的日志也安静通过，退出码 0
    other = tmp_path / "ok.log"
    other.write_text("all good\n", encoding="utf-8")
    r4 = invoke("check", "--file", str(other))
    assert r4.exit_code == 0


def test_add_stdin(store_env):
    r = invoke("add", input="someprog: error: disk full\n")
    assert r.exit_code == 0
    assert "已入库 1 条错误" in all_out(r)


def test_add_benign_text_not_recorded(store_env):
    r = invoke("add", input="everything fine\n")
    assert r.exit_code == 0
    assert "未识别到错误特征" in all_out(r)


def test_search_and_show(store_env, tmp_path):
    log = tmp_path / "err.log"
    log.write_text(CMAKE_ERR, encoding="utf-8")
    invoke("add", "--file", str(log))

    r1 = invoke("search", "GTest")
    assert r1.exit_code == 0
    assert "sig " in all_out(r1)

    sig = re.search(r"sig ([0-9a-f]{12})", all_out(r1)).group(1)
    r2 = invoke("show", sig[:8])
    assert r2.exit_code == 0
    assert "归一化签名" in all_out(r2)
    assert "CMake Error" in all_out(r2)


def test_solve_prefix_ambiguous(store_env, tmp_path):
    # 直接造两个同前缀的签名，验证 CLI 对模糊前缀的处理
    from errbook.store import Store

    store = Store(tmp_path / "cli.db")
    now = "2026-10-31T00:00:00+08:00"
    for i, (sid, tool) in enumerate([("aaa111", "cmake"), ("aaa222", "msvc")]):
        store.con.execute(
            "INSERT OR REPLACE INTO signatures(id, tool, norm_hash, normalized,"
            " fuzzy, count, first_seen, last_seen) VALUES(?,?,?,?,0,1,?,?)",
            (sid, tool, f"hash{i}", f"sig {i}", now, now),
        )
    store.con.commit()
    store.close()
    r = invoke("solve", "aaa", "nope")
    assert r.exit_code == 2
    assert "aaa111" in all_out(r) and "aaa222" in all_out(r)


def test_check_no_stdin_quiet(store_env):
    r = invoke("check")
    assert r.exit_code == 0


def test_top_and_forget(store_env, tmp_path):
    log = tmp_path / "err.log"
    log.write_text(CMAKE_ERR, encoding="utf-8")
    invoke("add", "--file", str(log))

    r1 = invoke("top")
    assert r1.exit_code == 0
    assert "· sig " in all_out(r1)  # 还没有修法

    sig = re.search(r"sig ([0-9a-f]{12})", all_out(r1)).group(1)
    invoke("solve", sig, "装 GTest")
    r2 = invoke("top")
    assert "✓ sig " in all_out(r2)

    r3 = invoke("forget", sig[:6])
    assert r3.exit_code == 0
    assert "已删除" in all_out(r3)

    r4 = invoke("top")
    assert "错题本还是空的" in all_out(r4)
    r5 = invoke("search", "GTest")
    assert "没搜到" in all_out(r5)


def test_run_missing_command_exit_127(store_env):
    r = invoke("run", "--", "definitely-not-a-command-xyz-987")
    assert r.exit_code == 127
    assert "找不到命令" in all_out(r)
    assert "Traceback" not in all_out(r)


def test_run_no_command_usage_error(store_env):
    r = invoke("run", "--")
    assert r.exit_code == 2


def test_check_does_not_create_db(store_env):
    db = store_env / "cli.db"
    r = invoke("check", input="someprog: error: disk full\n")
    assert r.exit_code == 0
    assert not db.exists()  # 查询型命令不建库


def test_check_missing_file_exit_2(store_env):
    r = invoke("check", "--file", store_env / "nope.log")
    assert r.exit_code == 2


def test_check_fuzzy_flag(store_env):
    text = "REMOTE CI LOG line1\nsome exotic failure format 42\n"
    invoke("add", "--raw", input=text)
    invoke("add", "--raw", input=text)  # 出现 2 次，满足提醒条件
    r1 = invoke("check", input=text)
    assert r1.exit_code == 0
    assert "sig" not in all_out(r1)  # 默认提取器认不出 raw 文本，也不出 fuzzy
    r2 = invoke("check", "--raw", input=text)  # raw 自带 fuzzy 含义
    assert r2.exit_code == 0
    assert "见过但没记过修法" in all_out(r2)


def test_add_raw_flag(store_env):
    body = "REMOTE CI LOG line1\nsome exotic failure format 42\n"
    r = invoke("add", "--raw", input=body)
    assert r.exit_code == 0
    assert "fuzzy" in all_out(r)
    # --raw 后同一文本可被命中（fuzzy 需要 --fuzzy 才显示，但入库成功）
    r2 = invoke("search", "exotic")
    assert "sig " in all_out(r2)


def test_add_conflicting_inputs(store_env, tmp_path):
    log = tmp_path / "a.log"
    log.write_text("x: error: y\n", encoding="utf-8")
    r = invoke("add", "inline text", "--file", str(log))
    assert r.exit_code == 2


def test_python_m_entry(store_env):
    import subprocess as sp

    env = {**os.environ, "ERRBOOK_DB": str(store_env / "cli.db")}
    out = sp.run(
        [sys.executable, "-m", "errbook", "--version"],
        capture_output=True, text=True, env=env,
    )
    assert out.returncode == 0
    assert __version__ in out.stdout
