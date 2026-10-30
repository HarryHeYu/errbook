"""自动脱敏（任务书 2.4）：形似 token/密钥的长随机串，存库前打码。

红线：错误摘录天然含源码、路径、密钥——errbook 纯本地零网络，
脱敏是为了让库本身少存一点不该存的东西。脱敏是确定性的，
同一个输入永远得到同一个输出，不影响签名稳定性。
"""

from __future__ import annotations

import re

MASK = "[masked]"

# 已知前缀的密钥/token
_KNOWN_RE = re.compile(
    r"\b(?:"
    r"sk-[A-Za-z0-9_-]{8,}"  # openai / deepseek 等风格
    r"|gh[pousr]_[A-Za-z0-9]{16,}"  # github token
    r"|github_pat_[A-Za-z0-9_]{20,}"
    r"|glpat-[A-Za-z0-9_-]{12,}"  # gitlab
    r"|xox[baprs]-[A-Za-z0-9-]{10,}"  # slack
    r"|AKIA[0-9A-Z]{16}"  # aws access key id
    r"|gsk_[A-Za-z0-9]{15,}"  # groq
    r"|hf_[A-Za-z0-9]{15,}"  # huggingface
    r"|eyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{5,}"  # jwt
    r")\b"
)

# 形如 "Bearer <token>"
_BEARER_RE = re.compile(r"(?i)\bbearer\s+[A-Za-z0-9._~+/=-]{8,}")

# Authorization 头
_AUTH_RE = re.compile(r"(?i)\bauthorization\s*[:=]\s*\S+")

# keyword: value 形态（token=xxx / API_KEY: xxx）
_KEYWORD_RE = re.compile(
    r"(?i)\b(token|secret|password|passwd|pwd|api[_-]?key|access[_-]?key|"
    r"private[_-]?key|client[_-]?secret|credential)s?\b(\s*[:=]\s*)(\S+)"
)

# 长随机串兜底：32 位以上纯 hex、40 位以上类 base64
_LONG_HEX_RE = re.compile(r"\b[0-9a-fA-F]{32,}\b")
_LONG_B64_RE = re.compile(r"\b[A-Za-z0-9+/]{40,}={0,2}\b")


def _keyword_sub(m: re.Match) -> str:
    val = m.group(3)
    if "/" in val or "\\" in val:  # 值像路径就别瞎打码
        return m.group(0)
    return f"{m.group(1)}{m.group(2)}{MASK}"


def redact(text: str) -> str:
    text = _KNOWN_RE.sub(MASK, text)
    text = _BEARER_RE.sub(MASK, text)
    text = _AUTH_RE.sub(MASK, text)
    text = _KEYWORD_RE.sub(_keyword_sub, text)
    text = _LONG_HEX_RE.sub(MASK, text)
    text = _LONG_B64_RE.sub(MASK, text)
    return text
