"""错误签名：归一化 + 稳定哈希（任务书 2.2，本项目的技术核心）。

设计立场：**签名诚实**。能归一的才归一，归不了的存原文并如实标
``fuzzy``，不假装智能匹配。

归一化剥离：路径、行号、十六进制地址、时间戳、PID、具体数值；
保留：错误类别 + 函数/符号名 + 消息骨架。已知错误代码
（C2065 / LNK2019 / E0425 / ERR_* 等）原样保留，不被当数值剥掉。

签名 = (tool, normalized_hash)，原文摘录始终保留在 occurrence 里，
命中展示时原文与历史修法并排，由人确认是否同款。
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass

__all__ = ["Extraction", "normalize_text", "signature_id"]


@dataclass
class Extraction:
    """一条从文本中提取出来的错误。"""

    tool: str
    excerpt: str  # 原文摘录（入库前由 store 再截断、脱敏）
    normalized: str  # 归一化后的消息骨架（单行）
    fuzzy: bool = False  # True 表示"没把握，只是存了原文"


# ---------------------------------------------------------------------------
# 归一化规则。顺序敏感：先吃掉结构化强的（URL/路径/时间戳），
# 再保护错误代码，最后才剥离裸数值。
# ---------------------------------------------------------------------------

_URL_RE = re.compile(r"\b(?:https?|ftp|file)://[^\s\"'`<>]+")

# msbuild 的行前缀 "1>"、"12>"——同一错误 msbuild 输出带前缀、直接跑 cl 不带
_MSBUILD_RE = re.compile(r"(?m)^\s*\d+>\s*")

# Windows 盘符路径 / UNC 路径。冒号与括号不允许出现在路径体里，
# 这样 "C:\x\main.c:5:2: error:" 会在正确的地方断开。
_WIN_PATH_RE = re.compile(r"\b[A-Za-z]:[\\/][^\s\"'`<>|*?:()]+")
_UNC_PATH_RE = re.compile(r"\\\\[^\s\"'`<>|*?:()]+")

# POSIX 路径（含 / 开头、./、../ 与多级相对路径）。必须有斜杠才算路径；
# 纯数字段（如 "50/50"）在替换函数里拒绝，避免误伤分数。
_POSIX_PATH_RE = re.compile(
    r"(?<![\w@+./-])"
    r"(?:"
    r"/(?:[\w@+.-]+/)*[\w@+.-]+"  # /usr/bin/ld
    r"|(?:\.{1,2}/)?(?:[\w@+.-]+/)+[\w@+.-]+"  # src/main.rs、./build/x
    r")"
    r"(?![\w@+./-])"
)

_ISO_TS_RE = re.compile(
    r"\b\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(?:[.,]\d+)?(?:Z|[+-]\d{2}:?\d{2})?\b"
)
_BRACKET_TS_RE = re.compile(r"[\[(]\d{1,3}:\d{2}:\d{2}(?:[.,]\d+)?[\])]")
_DATE_RE = re.compile(r"\b\d{4}-\d{2}-\d{2}\b")

_PID_RE = re.compile(r"(?i)\b(?:pid|process id)\b[=: ]+\d+")

_HEX_RE = re.compile(r"\b0[xX][0-9a-fA-F]+\b")

# 已知错误代码：msvc(C/LNK/CS/MSB/D/F/CL)、rustc(E0425 与 error[E0425])、
# node(ERR_*)、Windows(NT_STATUS_*)。归一化时原样保留。
_CODE_RE = re.compile(
    r"\[E\d{4,5}\]"
    r"|\b(?:C|LNK|CS|MSB|TS|CL|D|F|W|A|R|E)\d{4,6}\b"
    r"|\b(?:ERR|ER)_[A-Z0-9_]+\b"
    r"|\bNT_STATUS_[A-Z0-9_]+\b"
)

# 带单位/百分号的数值（先于裸数值处理，"2500MB" 与 "2.50 GiB" 都该变 N）
_UNIT_NUM_RE = re.compile(
    r"\b\d+(?:\.\d+)?\s?(?:GiB|MiB|KiB|TiB|GB|MB|KB|TB|B|bytes?|ms|us|ns|s)\b|"
    r"\b\d+(?:\.\d+)?%"
)
_PLAIN_NUM_RE = re.compile(r"(?<![\w.])\d+(?:\.\d+)?(?![\w.])")

# 行:列号（gcc/clang/rustc 的 "main.c:12:5"）。链式折叠成一个 :<N>，
# 这样带不带列号都落在同一个签名上。
_LINECOL_RE = re.compile(r":\d+(?::\d+)*(?![\w.])")

# msvc 的 "main.cpp(12)" / "main.cpp(12,5)"
_PAREN_LINE_RE = re.compile(r"\(\d+(?:,\d+)?\)")


def _protect_codes(text: str) -> tuple[str, dict[str, str]]:
    """把错误代码换占位符，防止后面的数值剥离误伤。

    占位符不能含数字（否则会被当数值剥掉），用私有区字符。
    """
    stash: dict[str, str] = {}

    def _stash(m: re.Match) -> str:
        token = m.group(0)
        key = f"\x01{chr(0xE000 + len(stash))}\x02"
        stash[key] = token
        return key

    return _CODE_RE.sub(_stash, text), stash


def _restore_codes(text: str, stash: dict[str, str]) -> str:
    for key, token in stash.items():
        text = text.replace(key, token)
    return text


def _url_sub(m: re.Match) -> str:
    return "<url>"


def _win_path_sub(m: re.Match) -> str:
    """路径只保留最后一段文件名：跨目录稳定（cwd 相对/绝对写法落到同一签名），
    又保留文件级区分度。"""
    base = re.split(r"[\\/]", m.group(0))[-1]
    return base or "<path>"


def _posix_path_sub(m: re.Match) -> str:
    s = m.group(0)
    if not re.search(r"[A-Za-z_]", s):  # "50/50" 这类纯数字不算路径
        return s
    return s.rsplit("/", 1)[-1] or "<path>"


def normalize_text(text: str) -> str:
    """把一段错误文本归一化成稳定的单行消息骨架。"""
    s = text

    s = _MSBUILD_RE.sub("", s)
    s = _URL_RE.sub(_url_sub, s)
    s = _WIN_PATH_RE.sub(_win_path_sub, s)
    s = _UNC_PATH_RE.sub(_win_path_sub, s)
    s = _POSIX_PATH_RE.sub(_posix_path_sub, s)

    s = _ISO_TS_RE.sub("<ts>", s)
    s = _BRACKET_TS_RE.sub("[<ts>]", s)
    s = _DATE_RE.sub("<date>", s)
    s = _PID_RE.sub("pid=<N>", s)
    s = _HEX_RE.sub("0xN", s)

    s, stash = _protect_codes(s)
    # 行号/括号行折叠要在裸数值剥离之前，保证 "file:12:5" 与 "file:12"
    # 落到同一个签名上
    s = _LINECOL_RE.sub(":<N>", s)
    s = _PAREN_LINE_RE.sub("(<N>)", s)
    s = _UNIT_NUM_RE.sub(lambda m: "N" + ("%" if m.group(0).endswith("%") else ""), s)
    s = _PLAIN_NUM_RE.sub("N", s)
    s = _restore_codes(s, stash)

    # 引号统一（" 与 ` 都折成 '），避免同一错误因引号风格不同而签名不同
    s = s.replace('"', "'").replace("`", "'")

    # 折叠空白成单行
    s = re.sub(r"\s+", " ", s).strip()
    return s


def signature_id(tool: str, normalized: str) -> tuple[str, str]:
    """签名 = (tool, normalized_hash)。返回 (sig_id, norm_hash)。

    sig_id 是稳定哈希的短前缀，用于 CLI 交互；norm_hash 保存全量。
    """
    norm_hash = hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:16]
    sig_id = hashlib.sha256(f"{tool}\x00{norm_hash}".encode("utf-8")).hexdigest()[:12]
    return sig_id, norm_hash
