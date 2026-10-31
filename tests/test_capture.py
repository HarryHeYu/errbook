import sys

import pytest

from errbook.capture import decode_output, run_wrapped


def test_decode_utf8():
    assert decode_output("héllo 世界".encode("utf-8")) == "héllo 世界"


def test_decode_utf8_bom():
    assert decode_output("\ufeffok".encode("utf-8")) == "ok"


def test_decode_gbk():
    # cp936 是显式尝试（先于 mbcs），任何平台都能解 GBK 字节
    assert decode_output("构建失败：找不到文件".encode("gbk")) == "构建失败：找不到文件"


def test_decode_utf16le_bom():
    raw = "构建失败：link.exe failed".encode("utf-16")  # 带 LE BOM
    assert decode_output(raw) == "构建失败：link.exe failed"


def test_decode_never_raises():
    out = decode_output(b"\xff\xfe\x81")
    assert isinstance(out, str)


def test_run_wrapped_missing_command():
    from errbook.capture import CommandNotFound

    with pytest.raises(CommandNotFound):
        run_wrapped(["definitely-not-a-command-xyz-987"])


def test_run_wrapped_passthrough_and_exit_code():
    rc, out, err = run_wrapped(
        [
            sys.executable,
            "-c",
            "import sys; print('stdout-line'); sys.stderr.write('stderr-line\\n'); raise SystemExit(3)",
        ]
    )
    assert rc == 3
    assert "stdout-line" in out
    assert "stderr-line" in err


def test_run_wrapped_large_output():
    rc, out, _ = run_wrapped([sys.executable, "-c", "print('x' * 200000)"])
    assert rc == 0
    assert len(out) >= 200000
