"""SQLite 单文件存储（任务书 2.4）：stdlib sqlite3 + FTS5，零第三方运行时依赖。

表：signatures / occurrences / fixes / projects。
多项目：occurrence 带 project（git remote 名或目录名），查询默认当前项目，
``--all`` 跨项目。摘录入库前截断 + 脱敏。

库的落点：默认 ``~/.errbook/errbook.db``，环境变量 ``ERRBOOK_DB`` 可覆盖
（测试与试验时把库指到别处，不污染家目录）。
"""

from __future__ import annotations

import os
import re
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Optional, Sequence

from .signature import Extraction, signature_id
from .trunc import truncate_excerpt

SCHEMA = """
CREATE TABLE IF NOT EXISTS projects(
  name TEXT PRIMARY KEY,
  created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS signatures(
  id TEXT PRIMARY KEY,
  tool TEXT NOT NULL,
  norm_hash TEXT NOT NULL,
  normalized TEXT NOT NULL,
  fuzzy INTEGER NOT NULL DEFAULT 0,
  count INTEGER NOT NULL DEFAULT 0,
  first_seen TEXT NOT NULL,
  last_seen TEXT NOT NULL,
  UNIQUE(tool, norm_hash)
);
CREATE TABLE IF NOT EXISTS occurrences(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  sig_id TEXT NOT NULL REFERENCES signatures(id) ON DELETE CASCADE,
  project TEXT NOT NULL,
  excerpt TEXT NOT NULL,
  ts TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS fixes(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  sig_id TEXT NOT NULL REFERENCES signatures(id) ON DELETE CASCADE,
  note TEXT NOT NULL,
  git_head TEXT,
  ts TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_occ_sig ON occurrences(sig_id);
CREATE INDEX IF NOT EXISTS idx_occ_proj ON occurrences(project);
CREATE INDEX IF NOT EXISTS idx_fix_sig ON fixes(sig_id);
"""


def now_iso() -> str:
    """本地时间 + 时区偏移，诚实且可排序。"""
    return datetime.now().astimezone().isoformat(timespec="seconds")


def fmt_ts(iso: str) -> str:
    """展示用："2026-10-31T00:41:22+08:00" → "2026-10-31 00:41"。"""
    return (iso or "")[:16].replace("T", " ")


def default_db_path() -> Path:
    env = os.environ.get("ERRBOOK_DB")
    if env:
        return Path(env)
    return Path.home() / ".errbook" / "errbook.db"


class SigNotFound(LookupError):
    pass


class AmbiguousSig(LookupError):
    def __init__(self, prefix: str, rows: list):
        self.prefix = prefix
        self.rows = rows
        super().__init__(f"prefix {prefix!r} matches {len(rows)} signatures")


class Store:
    def __init__(self, path: Optional[os.PathLike] = None):
        self.path = Path(path) if path is not None else default_db_path()
        parent = self.path.parent
        if str(parent):
            parent.mkdir(parents=True, exist_ok=True)
        self.con = sqlite3.connect(str(self.path), timeout=30.0)
        self.con.row_factory = sqlite3.Row
        self.con.execute("PRAGMA foreign_keys=ON")
        try:
            # WAL：单文件不变，读写并发友好（CI 多 job / agent 边跑边查）
            self.con.execute("PRAGMA journal_mode=WAL")
        except sqlite3.OperationalError:
            pass
        self.con.executescript(SCHEMA)
        self.fts_tokenizer = self._ensure_fts()

    def _ensure_fts(self):
        """FTS5 全文索引：trigram（支持中文子串）→ unicode61 → 无 FTS5 时
        返回 None，检索退化为 LIKE（Windows 官方 CPython ≤3.10 不带 FTS5）。"""
        try:
            self.con.execute(
                "CREATE VIRTUAL TABLE IF NOT EXISTS fts USING fts5("
                "sig_id UNINDEXED, kind UNINDEXED, body, tokenize='trigram')"
            )
            return "trigram"
        except sqlite3.OperationalError:
            pass
        try:
            self.con.execute(
                "CREATE VIRTUAL TABLE IF NOT EXISTS fts USING fts5("
                "sig_id UNINDEXED, kind UNINDEXED, body)"
            )
            return "unicode61"
        except sqlite3.OperationalError:
            return None

    def close(self) -> None:
        self.con.close()

    # ------------------------------------------------------------------
    # 写入
    # ------------------------------------------------------------------

    def record(self, items: Sequence[Extraction], project: str) -> list[dict]:
        """错误入库：签名 upsert、occurrence 追加、FTS 索引。同一次采集内去重。"""
        now = now_iso()
        results: list[dict] = []
        seen: set[str] = set()
        for it in items:
            # 脱敏已在 extract_all 源头完成；这里只做截断
            excerpt = truncate_excerpt(it.excerpt)
            normalized = it.normalized
            sig_id, norm_hash = signature_id(it.tool, normalized)
            if sig_id in seen:
                continue
            seen.add(sig_id)
            cur = self.con.execute(
                "SELECT count FROM signatures WHERE id = ?", (sig_id,)
            ).fetchone()
            is_new = cur is None
            if is_new:
                self.con.execute(
                    "INSERT INTO signatures(id, tool, norm_hash, normalized, fuzzy,"
                    " count, first_seen, last_seen) VALUES(?,?,?,?,?,1,?,?)",
                    (sig_id, it.tool, norm_hash, normalized, int(it.fuzzy), now, now),
                )
            else:
                self.con.execute(
                    "UPDATE signatures SET count = count + 1, last_seen = ? WHERE id = ?",
                    (now, sig_id),
                )
            self.con.execute(
                "INSERT INTO occurrences(sig_id, project, excerpt, ts) VALUES(?,?,?,?)",
                (sig_id, project, excerpt, now),
            )
            # FTS 只收录每签名不重复的摘录，重复出现不再膨胀索引
            if self.fts_tokenizer:
                seen_body = self.con.execute(
                    "SELECT 1 FROM fts WHERE sig_id = ? AND body = ? LIMIT 1",
                    (sig_id, excerpt),
                ).fetchone()
                if not seen_body:
                    self.con.execute(
                        "INSERT INTO fts(sig_id, kind, body) VALUES(?, 'excerpt', ?)",
                        (sig_id, excerpt),
                    )
            self.con.execute(
                "INSERT OR IGNORE INTO projects(name, created_at) VALUES(?,?)",
                (project, now),
            )
            count = self.con.execute(
                "SELECT count FROM signatures WHERE id = ?", (sig_id,)
            ).fetchone()["count"]
            results.append(
                {
                    "sig_id": sig_id,
                    "tool": it.tool,
                    "fuzzy": bool(it.fuzzy),
                    "new": is_new,
                    "count": count,
                    "normalized": normalized,
                    "excerpt": excerpt,
                }
            )
        self.con.commit()
        return results

    def add_fix(self, sig_id: str, note: str, git_head: Optional[str] = None) -> None:
        now = now_iso()
        self.con.execute(
            "INSERT INTO fixes(sig_id, note, git_head, ts) VALUES(?,?,?,?)",
            (sig_id, note, git_head, now),
        )
        if self.fts_tokenizer:
            self.con.execute(
                "INSERT INTO fts(sig_id, kind, body) VALUES(?, 'fix', ?)", (sig_id, note)
            )
        self.con.commit()

    def forget(self, prefix: str) -> sqlite3.Row:
        """删除一个签名（连同出现记录与修法）。错入库也要能出库。"""
        sig = self.resolve_sig(prefix)
        self.con.execute("DELETE FROM fts WHERE sig_id = ?", (sig["id"],))
        self.con.execute("DELETE FROM signatures WHERE id = ?", (sig["id"],))
        self.con.commit()
        return sig

    # ------------------------------------------------------------------
    # 查询
    # ------------------------------------------------------------------

    def fixes_for(self, sig_id: str) -> list:
        return self.con.execute(
            "SELECT * FROM fixes WHERE sig_id = ? ORDER BY ts DESC, id DESC",
            (sig_id,),
        ).fetchall()

    def occurrences_for(self, sig_id: str, limit: int = 5) -> list:
        return self.con.execute(
            "SELECT * FROM occurrences WHERE sig_id = ? ORDER BY ts DESC, id DESC LIMIT ?",
            (sig_id, limit),
        ).fetchall()

    def find_by_prefix(self, prefix: str) -> list:
        return self.con.execute(
            "SELECT * FROM signatures WHERE id LIKE ? ORDER BY id",
            (prefix.replace("%", "").replace("_", "") + "%",),
        ).fetchall()

    def resolve_sig(self, prefix: str) -> sqlite3.Row:
        prefix = prefix.strip().replace("%", "").replace("_", "").strip()
        if not prefix:
            raise SigNotFound(prefix)
        rows = self.find_by_prefix(prefix)
        if not rows:
            raise SigNotFound(prefix)
        if len(rows) > 1:
            raise AmbiguousSig(prefix, rows)
        return rows[0]

    def _in_project(self, sig_id: str, project: str) -> bool:
        return (
            self.con.execute(
                "SELECT 1 FROM occurrences WHERE sig_id = ? AND project = ? LIMIT 1",
                (sig_id, project),
            ).fetchone()
            is not None
        )

    def find_hits(
        self,
        extractions: Sequence[Extraction],
        project: Optional[str] = None,
        include_fuzzy: bool = False,
    ) -> list[dict]:
        """check / run 的命中查询。

        分级匹配：唯一的一层是 tool+归一化哈希的精确签名，"更粗的一级"
        由 fuzzy 签名承担（默认隐藏、人工确认），不做模糊哈希近似。

        提醒条件（任务书 2.3 + 风险表）：有 solve 记录，或出现 ≥2 次但
        还没修法（按项目范围计数）；fuzzy 签名默认不出。
        """
        hits: list[dict] = []
        for ext in extractions:
            sig_id, _ = signature_id(ext.tool, ext.normalized)
            row = self.con.execute(
                "SELECT * FROM signatures WHERE id = ?", (sig_id,)
            ).fetchone()
            if row is None:
                continue
            if row["fuzzy"] and not include_fuzzy:
                continue
            if project is not None:
                scope_count = self.con.execute(
                    "SELECT COUNT(*) AS c FROM occurrences WHERE sig_id = ? AND project = ?",
                    (sig_id, project),
                ).fetchone()["c"]
                if scope_count == 0:
                    continue
            else:
                scope_count = row["count"]
            fixes = self.fixes_for(sig_id)
            if not fixes and scope_count < 2:
                continue
            hits.append({"sig": row, "fixes": fixes, "extraction": ext})
        return hits

    def search(
        self, query: str, project: Optional[str] = None, limit: int = 20
    ) -> list[dict]:
        """FTS 全文搜索错误摘录与修法；太短的词退回 LIKE。

        FTS 命中保持相关性（rank）顺序；LIKE 兜底按出现次数排序。
        """
        rows: list[dict] = []
        if self.fts_tokenizer:
            q = self._fts_query(query)
            if q:
                try:
                    fts_rows = self.con.execute(
                        "SELECT sig_id, snippet(fts, 2, '[', ']', '…', 10) AS snip"
                        " FROM fts WHERE fts MATCH ? ORDER BY rank LIMIT ?",
                        (q, limit * 8),
                    ).fetchall()
                except sqlite3.OperationalError:
                    fts_rows = []
                best: dict[str, str] = {}
                for fr in fts_rows:
                    best.setdefault(fr["sig_id"], fr["snip"])
                for sig_id, snip in best.items():
                    row = self.con.execute(
                        "SELECT * FROM signatures WHERE id = ?", (sig_id,)
                    ).fetchone()
                    if row is None:
                        continue
                    if project is not None and not self._in_project(sig_id, project):
                        continue
                    rows.append({**dict(row), "snippet": snip})
        if not rows:
            rows = self._like_fallback(query, project, limit)
        return rows[:limit]

    def _fts_query(self, query: str) -> str:
        tokens = [t.replace('"', "") for t in re.findall(r"[^\s]{3,}", query)]
        return " ".join(f'"{t}"' for t in tokens if t)

    def _like_fallback(
        self, query: str, project: Optional[str], limit: int
    ) -> list[dict]:
        needle = query.strip()
        if not needle:
            return []
        pat = f"%{needle}%"
        sig_ids: list[str] = [
            r["id"]
            for r in self.con.execute(
                "SELECT id FROM signatures WHERE normalized LIKE ?", (pat,)
            )
        ]
        sig_ids += [
            r["sig_id"]
            for r in self.con.execute(
                "SELECT DISTINCT sig_id FROM occurrences WHERE excerpt LIKE ?", (pat,)
            )
        ]
        sig_ids += [
            r["sig_id"]
            for r in self.con.execute(
                "SELECT DISTINCT sig_id FROM fixes WHERE note LIKE ?", (pat,)
            )
        ]
        out: list[dict] = []
        for sig_id in dict.fromkeys(sig_ids):
            row = self.con.execute(
                "SELECT * FROM signatures WHERE id = ?", (sig_id,)
            ).fetchone()
            if row is None:
                continue
            if project is not None and not self._in_project(sig_id, project):
                continue
            out.append({**dict(row), "snippet": ""})
            if len(out) >= limit:
                break
        out.sort(key=lambda r: r["count"], reverse=True)
        return out

    def top(self, project: Optional[str] = None, limit: int = 10) -> list[dict]:
        """高频错误排行。默认当前项目；--all 跨项目。"""
        if project is not None:
            rows = self.con.execute(
                "SELECT s.*, COUNT(o.id) AS scope_count FROM signatures s"
                " JOIN occurrences o ON o.sig_id = s.id AND o.project = ?"
                " GROUP BY s.id ORDER BY scope_count DESC, s.count DESC LIMIT ?",
                (project, limit),
            ).fetchall()
        else:
            rows = self.con.execute(
                "SELECT s.*, s.count AS scope_count FROM signatures s"
                " ORDER BY s.count DESC LIMIT ?",
                (limit,),
            ).fetchall()
        out = []
        for r in rows:
            d = dict(r)
            d["fix_count"] = self.con.execute(
                "SELECT COUNT(*) AS c FROM fixes WHERE sig_id = ?", (r["id"],)
            ).fetchone()["c"]
            out.append(d)
        return out
