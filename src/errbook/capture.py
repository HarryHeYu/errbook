"""run -- 包装器（任务书 2.1）：透传原始输出（字节原样转发），同时捕获入库。

退出码、内容都不改——它必须是安全的默认包装，agent 和人都可以
无脑替换原命令。按字节读、``errors="replace"``，Windows GBK 构建
输出也能解（任务书风险表：MBCS 探测）。errbook 自身的提示只写
stderr，stdout 永远只有子进程的输出。
"""

from __future__ import annotations

import locale
import os
import subprocess
import sys
from threading import Thread
from typing import List, Tuple


class CommandNotFound(Exception):
    """包装的命令不存在或不可执行（对齐 shell 的 rc=127 语义）。"""

    def __init__(self, cmd: str):
        self.cmd = cmd
        super().__init__(f"command not found: {cmd}")


def decode_output(raw: bytes) -> str:
    """构建输出按字节读，尽力解码：BOM → UTF-8 → GBK → MBCS/本地编码。"""
    if not raw:
        return ""
    if raw.startswith(b"\xef\xbb\xbf"):
        try:
            return raw.decode("utf-8-sig")
        except UnicodeDecodeError:
            pass
    if raw.startswith(b"\xff\xfe"):  # PowerShell 重定向默认 UTF-16LE
        return raw.decode("utf-16", errors="replace")
    if raw.startswith(b"\xfe\xff"):
        return raw[2:].decode("utf-16-be", errors="replace")
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        pass
    try:
        return raw.decode("cp936")  # GBK 常见构建输出（与系统 ACP 无关）
    except UnicodeDecodeError:
        pass
    enc = "mbcs" if os.name == "nt" else locale.getpreferredencoding(False)
    try:
        return raw.decode(enc, errors="replace")
    except (LookupError, UnicodeDecodeError):
        return raw.decode("utf-8", errors="replace")


def run_wrapped(cmd: List[str]) -> Tuple[int, str, str]:
    """跑命令：stdout/stderr 字节透传 + 捕获。返回 (returncode, stdout, stderr)。"""
    try:
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    except (FileNotFoundError, NotADirectoryError, PermissionError):
        raise CommandNotFound(cmd[0])
    out_buf = bytearray()
    err_buf = bytearray()

    def pump(src, buf: bytearray, sink) -> None:
        try:
            while True:
                chunk = src.read(8192)
                if not chunk:
                    break
                buf.extend(chunk)
                try:
                    sink.write(chunk)
                    sink.flush()
                except BrokenPipeError:
                    pass  # 下游关管（| head）：继续收完子进程输出，只是不再转发
        finally:
            src.close()

    t_out = Thread(target=pump, args=(proc.stdout, out_buf, sys.stdout.buffer), daemon=True)
    t_err = Thread(target=pump, args=(proc.stderr, err_buf, sys.stderr.buffer), daemon=True)
    t_out.start()
    t_err.start()
    try:
        rc = proc.wait()
    except KeyboardInterrupt:
        proc.kill()
        rc = 130
    t_out.join()
    t_err.join()
    return rc, decode_output(bytes(out_buf)), decode_output(bytes(err_buf))
