"""常见真实错误样本（M0 测试用；M2 的完整样本库在 tests/fixtures/）。"""

CMAKE_ERR = """\
-- The C compiler identification is GNU 13.2.0
-- Detecting C compiler ABI info - done
CMake Error at CMakeLists.txt:5 (find_package):
  By not providing "FindGTest.cmake" in CMAKE_MODULE_PATH this project has
  asked CMake to find a package configuration file provided by "GTest", but
  CMake did not find one.

  Could not find a package configuration file provided by "GTest" with any
  of the following names:

    FindGTest.cmake
    gtest-config.cmake

  Add the installation prefix of "GTest" to CMAKE_PREFIX_PATH or set
  "GTest_DIR" to a directory containing one of the above files.  If "GTest"
  provides a separate development package or SDK, be sure it has been
  installed.
-- Configuring incomplete, errors occurred!
"""

PYTHON_TB = """\
Traceback (most recent call last):
  File "train.py", line 42, in <module>
    model = build_model(cfg)
  File "model.py", line 10, in build_model
    return nn.Linear(16, 8)
NameError: name 'nn' is not defined
"""

PYTHON_TB_VARIANT = """\
Traceback (most recent call last):
  File "D:\\work\\other.py", line 99, in <module>
    train()
  File "D:\\work\\model.py", line 3, in train
    return nn.Linear(9999, 1)
NameError: name 'nn' is not defined
"""

PYTEST_ERR = """\
=================================== FAILURES ===================================
_________________________________ test_adder ___________________________________

    def test_adder():
>       assert add(1, 2) == 4
E       AssertionError: assert 3 == 4
E        +  where 3 = add(1, 2)

test_calc.py:6: AssertionError
=========================== short summary info ============================
FAILED test_calc.py::test_adder - AssertionError: assert 3 == 4
"""
