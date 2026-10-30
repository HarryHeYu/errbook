"""run -- 包装器（任务书 2.1）：透传原始输出（字节原样转发），同时捕获入库。

退出码、内容都不改——它必须是安全的默认包装，agent 和人都可以
无脑替换原命令。按字节读、``errors="replace"``，Windows GBK 构建
输出也能解（任务书风险表：MBCS 探测）。
"""

from __future__ import annotations

import locale
import os
import subprocess
import sys
from threading import Thread
from typing import List, Tuple


def decode_output(raw: bytes) -> str:
    """构建输出按字节读，尽力解码：UTF-8 优先，失败退 MBCS / 本地编码。"""
    if not raw:
        return ""
    if raw.startswith(b"\xef\xbb\xbf"):
        try:
            return raw.decode("utf-8-sig")
        except UnicodeDecodeError:
            pass
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        pass
    enc = "mbcs" if os.name == "nt" else locale.getpreferredencoding(False)
    try:
        return raw.decode(enc, errors="replace")
    except (LookupError, UnicodeDecodeError):
        return raw.decode("utf-8", errors="replace")


def run_wrapped(cmd: List[str]) -> Tuple[int, str, str]:
    """跑命令：stdout/stderr 字节透传 + 捕获。返回 (returncode, stdout, stderr)。"""
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    out_buf = bytearray()
    err_buf = bytearray()

    def pump(src, buf: bytearray, sink) -> None:
        try:
            while True:
                chunk = src.read(8192)
                if not chunk:
                    break
                buf.extend(chunk)
                sink.write(chunk)
                sink.flush()
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
