import pytest

import errbook.store  # noqa: F401  确保导入可行

@pytest.fixture()
def store_env(tmp_path, monkeypatch):
    """CLI 测试用的隔离数据库（落在仓库内 .pytest_tmp）。"""
    monkeypatch.setenv("ERRBOOK_DB", str(tmp_path / "cli.db"))
    return tmp_path


@pytest.fixture()
def store(tmp_path, store_env):
    from errbook.store import Store

    s = Store(tmp_path / "unit.db")
    yield s
    s.close()


def all_out(result) -> str:
    """CliRunner 的 stdout + stderr（click 版本差异兜底）。"""
    out = result.output or ""
    try:
        out += result.stderr or ""
    except Exception:
        pass
    return out
