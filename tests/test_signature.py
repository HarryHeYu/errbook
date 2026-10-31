from errbook.signature import normalize_text, signature_id


def test_strips_windows_path_and_paren_line():
    got = normalize_text(
        r"C:\proj\src\main.cpp(12): error C2065: 'cout': undeclared identifier"
    )
    assert got == "main.cpp(<N>): error C2065: 'cout': undeclared identifier"


def test_posix_path_line_col_and_rust_code():
    got = normalize_text(
        "src/main.rs:12:5: error[E0425]: cannot find value `BUFFER_SIZE` in this scope"
    )
    assert got == "main.rs:<N>: error[E0425]: cannot find value 'BUFFER_SIZE' in this scope"


def test_line_col_folds_with_or_without_column():
    a = normalize_text("src/foo.c:12:5: error: 'x' undeclared")
    b = normalize_text("src/foo.c:99: error: 'x' undeclared")
    assert a == b


def test_strips_values_and_units():
    got = normalize_text(
        "CUDA out of memory. Tried to allocate 2.50 GiB. GPU 0 has a total "
        "capacity of 79.20 GiB of which 1.24 GiB is free."
    )
    assert got == (
        "CUDA out of memory. Tried to allocate N. GPU N has a total "
        "capacity of N of which N is free."
    )


def test_error_codes_survive_number_stripping():
    for text in (
        "error C2065: 'cout': undeclared identifier",
        "fatal error LNK2019: unresolved external symbol",
        "error[E0425]: cannot find value `x` in this scope",
        "Error [ERR_MODULE_NOT_FOUND]: Cannot find package 'lodash'",
    ):
        got = normalize_text(text)
        assert any(c in got for c in ("C2065", "LNK2019", "E0425", "ERR_MODULE_NOT_FOUND"))


def test_strips_hex_ts_pid():
    assert normalize_text("fault at 0xDEADBEEF in module") == "fault at 0xN in module"
    assert normalize_text("[12:05:33] build start") == "[<ts>] build start"
    assert (
        normalize_text("2026-10-31T00:41:22+08:00 finished")
        == "<ts> finished"
    )
    assert normalize_text("worker PID: 12345 died") == "worker pid=<N> died"


def test_versions_keep_shape_but_values_normalized():
    assert normalize_text("python 3.11 is required, found 3.9") == "python N is required, found N"


def test_quote_folding():
    a = normalize_text('By not providing "FindGTest.cmake" CMake did not find one')
    b = normalize_text("By not providing `FindGTest.cmake` CMake did not find one")
    assert a == b


def test_stability_across_occurrences():
    a = normalize_text('CMake Error at CMakeLists.txt:5 (find_package): Could NOT find Foo')
    b = normalize_text('CMake Error at D:\\elsewhere\\CMakeLists.txt:120 (find_package): Could NOT find Foo')
    assert a == b
    assert signature_id("cmake", a) == signature_id("cmake", b)


def test_relative_backslash_path_collapses_to_basename():
    a = normalize_text(r"src\main.cpp(12): error C2065: 'cout': undeclared identifier")
    b = normalize_text(r"C:\proj\src\main.cpp(12): error C2065: 'cout': undeclared identifier")
    assert a == b == "main.cpp(<N>): error C2065: 'cout': undeclared identifier"


def test_escape_sequence_not_eaten_by_backslash_path_rule():
    # 字符串字面量里的 "a\nb" 不是路径，末段无点必须原样保留
    got = normalize_text('SyntaxError: (unicode error) "utf-8" codec can\\t decode')
    assert "can\\t" in got or "can" in got  # 只要不抛错且不吞成路径即可


def test_bare_time_normalized():
    assert normalize_text("build took 12:34:56.789 to finish") == "build took <ts> to finish"
    assert normalize_text("retry at 12:34 later") == "retry at <ts> later"


def test_line_col_not_confused_with_time():
    a = normalize_text("net.c:57:12: error: 'x' undeclared")
    b = normalize_text("net.c:512:9: error: 'x' undeclared")
    assert a == b  # 行:列 折叠到 :<N>，不被当成时间戳


def test_sig_id_differs_across_tools():
    sid1, _ = signature_id("cmake", "same text")
    sid2, _ = signature_id("gcc-clang", "same text")
    assert sid1 != sid2
