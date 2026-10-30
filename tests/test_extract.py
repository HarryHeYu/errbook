from errbook.extract import extract_all

from .samples import CMAKE_ERR, PYTEST_ERR, PYTHON_TB, PYTHON_TB_VARIANT


def test_python_traceback_basic():
    exts = extract_all(PYTHON_TB)
    assert len(exts) == 1
    e = exts[0]
    assert e.tool == "python-traceback"
    assert not e.fuzzy
    assert e.normalized == "NameError: name 'nn' is not defined"
    assert "build_model" in e.excerpt  # 原文摘录完整保留


def test_python_traceback_variant_same_signature():
    a = extract_all(PYTHON_TB)[0]
    b = extract_all(PYTHON_TB_VARIANT)[0]
    assert a.normalized == b.normalized


def test_python_chained_exception_takes_last():
    text = """\
Traceback (most recent call last):
  File "a.py", line 5, in load
    import config
ImportError: No module named config

During handling of the above exception, another exception occurred:

Traceback (most recent call last):
  File "a.py", line 3, in <module>
    load()
RuntimeError: config missing
"""
    exts = extract_all(text)
    assert len(exts) == 1
    assert exts[0].normalized == "RuntimeError: config missing"


def test_pytest_e_lines():
    exts = extract_all(PYTEST_ERR)
    assert any(
        e.tool == "python-traceback" and "assert" in e.normalized for e in exts
    )


def test_cmake_error_block():
    exts = extract_all(CMAKE_ERR)
    assert len(exts) == 1
    e = exts[0]
    assert e.tool == "cmake"
    assert not e.fuzzy
    assert e.normalized.startswith("CMake Error at CMakeLists.txt:<N> (find_package):")
    assert "GTest" in e.normalized


def test_generic_error_line():
    text = "someprog: error: something failed badly\n"
    exts = extract_all(text)
    assert len(exts) == 1
    e = exts[0]
    assert e.tool == "generic"
    assert not e.fuzzy
    assert e.normalized == "someprog: error: something failed badly"


def test_generic_make_error():
    exts = extract_all("make: *** [Makefile:12: all] Error 1\n")
    assert len(exts) == 1
    assert exts[0].tool == "generic"
    assert exts[0].normalized == "make: *** [Makefile:<N>: all] Error N"


def test_generic_repeated_lines_fuzzy():
    text = "\n".join(["Warning: something weird happened"] * 5) + "\n"
    exts = extract_all(text)
    assert len(exts) == 1
    e = exts[0]
    assert e.tool == "generic"
    assert e.fuzzy


def test_benign_text_not_recorded():
    assert extract_all("everything is fine\nbuild ok\n") == []
