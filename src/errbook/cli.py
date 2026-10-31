"""errbook 命令行（Typer）。人能直接用；agent 通过 SKILL.md 接同一套命令，
不存在第二套逻辑。"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Optional

import typer

from . import __version__
from .capture import CommandNotFound, decode_output, run_wrapped
from .check import check_text
from .extract import extract_all
from .project import detect_project, git_head
from .signature import Extraction, normalize_text
from .store import AmbiguousSig, SigNotFound, Store, default_db_path, fmt_ts

# Windows 控制台编码兜底：打印别的终端贴进来的字符不炸；
# 管道场景（非 tty）统一 UTF-8，方便 agent / CI 解析
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        try:
            if not _stream.isatty():
                _stream.reconfigure(encoding="utf-8", errors="replace")
            else:
                _stream.reconfigure(errors="replace")
        except (ValueError, OSError):
            pass

app = typer.Typer(
    help="errbook · 构建错误错题本 —— 错误按签名归档，修法跟着错误走。",
    no_args_is_help=True,
    add_completion=False,
)


def _version_callback(value: bool) -> None:
    if value:
        typer.echo(f"errbook {__version__}")
        raise typer.Exit()


@app.callback()
def _root(
    version: bool = typer.Option(
        False, "--version", "-V", callback=_version_callback, is_eager=True, help="显示版本号。"
    ),
) -> None:
    """errbook · 构建错误错题本。纯本地、零网络。"""


def _resolve_sig(store: Store, prefix: str):
    try:
        return store.resolve_sig(prefix)
    except SigNotFound:
        typer.secho(
            f"errbook: 找不到签名 {prefix}（用 errbook search / top 找找）。",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(1)
    except AmbiguousSig as e:
        typer.secho(
            f"errbook: 前缀 {prefix} 对应多个签名，请写长一点：",
            fg=typer.colors.YELLOW,
            err=True,
        )
        for r in e.rows:
            typer.echo(f"  {r['id']} · {r['tool']} · {r['normalized'][:80]}", err=True)
        raise typer.Exit(2)


def _open_readonly_store():
    """查询型命令不建库：库不存在就当空的（只读容器 / 首次使用都安静）。"""
    if not default_db_path().exists():
        return None
    return Store()


@app.command("run", context_settings={"allow_extra_args": True, "ignore_unknown_options": True})
def run(ctx: typer.Context) -> None:
    """包装任意构建/运行命令：透传原始输出与退出码，捕获的错误自动入库。

    用法：errbook run -- <command> [args...]

    退出码、输出内容都不改——可以无脑替换原命令。错误命中历史时，
    会在输出之后追加提醒块（stderr）。
    """
    cmd = list(ctx.args)
    while cmd and cmd[0] == "--":
        cmd.pop(0)
    if not cmd:
        raise typer.BadParameter("用法：errbook run -- <command> [args...]")

    try:
        rc, out, err = run_wrapped(cmd)
    except CommandNotFound as e:
        typer.secho(f"errbook: 找不到命令：{e.cmd}", fg=typer.colors.RED, err=True)
        raise typer.Exit(127)

    combined = out + "\n" + err
    extractions = extract_all(combined) if combined.strip() else []
    try:
        if extractions:
            store = Store()
            project = detect_project()
            results = store.record(extractions, project=project)
            new_count = sum(1 for r in results if r["new"])
            typer.secho(
                f"errbook: 已入库 {len(results)} 条错误"
                f"（新增 {new_count} · 已知 {len(results) - new_count}）",
                fg=typer.colors.CYAN,
                err=True,
            )
            # 逐条列出 sig-id——solve 是灵魂步骤，入口不能断
            for r in results:
                mark = "+" if r["new"] else "="
                times = "新增" if r["new"] else f"第 {r['count']} 次"
                typer.echo(f"  {mark} sig {r['sig_id']} · {r['tool']} · {times}", err=True)
            blocks, _ = check_text(store, combined, project=project, extractions=extractions)
            if blocks:
                typer.echo(blocks, err=True)
    except BrokenPipeError:
        pass
    if rc < 0:
        # POSIX 信号死亡：按 shell 惯例 128+N
        rc = 128 - rc
    raise typer.Exit(rc)


@app.command("add")
def add(
    text: Optional[str] = typer.Argument(None, help="错误文本；也可用 --file 或管道 stdin。"),
    file: Optional[Path] = typer.Option(None, "--file", "-f", help="从文件读取错误文本（自动探测编码）。"),
    raw: bool = typer.Option(
        False, "--raw", help="整段按 fuzzy 签名入库，跳过提取器（远程 CI 日志等认不出格式的场景）。"
    ),
) -> None:
    """手动/agent 粘贴一段错误文本入库（错误来自无法包装的场景，如远程 CI 日志）。"""
    if file is not None and text is not None:
        raise typer.BadParameter("--file 和位置文本只能给一个。")
    if file is not None:
        if not file.exists():
            raise typer.BadParameter(f"文件不存在：{file}")
        body = decode_output(file.read_bytes())
    elif text is not None:
        body = text
    elif not sys.stdin.isatty():
        body = decode_output(sys.stdin.buffer.read())
    else:
        raise typer.BadParameter("没有输入：传位置参数、--file，或用管道喂 stdin。")

    if not body.strip():
        raise typer.BadParameter("输入为空。")

    if raw:
        # 诚实兜底：不假装认识格式，整段存原文标 fuzzy
        extractions = [
            Extraction(tool="generic", excerpt=body, normalized=normalize_text(body), fuzzy=True)
        ]
    else:
        extractions = extract_all(body)
        if not extractions:
            typer.echo(
                "errbook: 未识别到错误特征，未入库（确定要存就用 --raw，或贴错误本身比贴整段日志更准）。"
            )
            return

    store = Store()
    project = detect_project()
    results = store.record(extractions, project=project)
    typer.echo(f"errbook: 已入库 {len(results)} 条错误：")
    for r in results:
        fuzzy = " · fuzzy（归一化没把握）" if r["fuzzy"] else ""
        typer.echo(f"  sig {r['sig_id']} · {r['tool']} · 出现 {r['count']} 次{fuzzy}")
        typer.echo(f"      {r['normalized'][:110]}")
    typer.echo('修好之后记得：errbook solve <sig-id> "怎么好的" —— 漏了等于白修。')
    blocks, _ = check_text(store, body, project=project, extractions=extractions)
    if blocks:
        typer.echo(blocks)


@app.command("solve")
def solve(
    sig_id: str = typer.Argument(..., help="签名 ID，可只写前缀。"),
    note: str = typer.Argument(..., help="怎么好的，一句话。不同根因就再 solve 一次，会追加成列表。"),
) -> None:
    """给某个签名附记修复方法（错题本的灵魂步骤，漏了等于白修）。"""
    store = Store()
    sig = _resolve_sig(store, sig_id)
    head = git_head()
    store.add_fix(sig["id"], note, git_head=head)
    git_note = f"（git:{head[:7]}）" if head else ""
    typer.echo(f"errbook: 已记录修法{git_note} —— sig {sig['id']} · {sig['tool']}")
    typer.echo(f"  {note}")


@app.command("check")
def check(
    file: Optional[Path] = typer.Option(None, "--file", "-f", help="读文件而不是 stdin。"),
    all_: bool = typer.Option(False, "--all", help="跨项目匹配。"),
    fuzzy: bool = typer.Option(False, "--fuzzy", help="包含 fuzzy 签名（默认不出——不假装匹配得准）。"),
    raw: bool = typer.Option(False, "--raw", help="整段当一个 fuzzy 签名比对（配合 add --raw 入库的远程日志）。"),
) -> None:
    """读一段错误文本（stdin 或 --file），命中历史时输出提醒块。

    退出码恒为 0——它是信息附加器，不是质量门禁；唯一例外是 --file
    指向不存在的文件（用法错误，返回 2）。提醒条件：有 solve 记录，
    或同一签名出现 ≥2 次但还没修法。
    """
    if file is not None:
        if not file.exists():
            typer.secho(f"errbook: 文件不存在：{file}", fg=typer.colors.RED, err=True)
            raise typer.Exit(2)
        body = decode_output(file.read_bytes())
    elif not sys.stdin.isatty():
        body = decode_output(sys.stdin.buffer.read())
    else:
        raise typer.Exit(0)  # 没输入也安静通过——信息附加器，绝不挡路

    if raw:
        # 与 add --raw 对称：整段当一个 fuzzy 签名比对（raw 自带 fuzzy 含义）
        extractions = [
            Extraction(tool="generic", excerpt=body, normalized=normalize_text(body), fuzzy=True)
        ]
    else:
        extractions = extract_all(body)

    store = _open_readonly_store()
    if store is None:
        raise typer.Exit(0)  # 还没有错题本，自然无历史可提
    blocks, _ = check_text(
        store,
        body,
        project=None if all_ else detect_project(),
        include_fuzzy=fuzzy or raw,
        extractions=extractions,
    )
    if blocks:
        typer.echo(blocks)
    raise typer.Exit(0)


@app.command("search")
def search(
    query: str = typer.Argument(..., help="全文关键词（FTS，中文子串也行）。"),
    all_: bool = typer.Option(False, "--all", help="跨项目。"),
    limit: int = typer.Option(20, "--limit", "-n", min=1, help="最多返回几条。"),
) -> None:
    """FTS 全文搜索错误摘录与修法。"""
    store = _open_readonly_store()
    rows = store.search(query, project=None if all_ else detect_project(), limit=limit) if store else []
    if not rows:
        typer.echo("errbook: 没搜到。换个更短的关键词试试。")
        return
    for r in rows:
        typer.secho(
            f"sig {r['id']} · {r['tool']} · 出现 {r['count']} 次 · 最近 {fmt_ts(r['last_seen'])}",
            fg=typer.colors.CYAN,
        )
        typer.echo(f"  {r['normalized'][:120]}")
        if r.get("snippet"):
            typer.echo(f"  ↳ {r['snippet'][:140]}")


@app.command("show")
def show(sig_id: str = typer.Argument(..., help="签名 ID，可只写前缀。")) -> None:
    """看一个签名的完整档案：归一化签名、修法列表、出现记录。"""
    store = Store()
    sig = _resolve_sig(store, sig_id)
    typer.secho(
        f"sig {sig['id']} · {sig['tool']} · 出现 {sig['count']} 次"
        + (" · fuzzy" if sig["fuzzy"] else ""),
        fg=typer.colors.CYAN,
    )
    typer.echo(f"首次 {fmt_ts(sig['first_seen'])} · 最近 {fmt_ts(sig['last_seen'])}")
    typer.echo("归一化签名：")
    typer.echo(f"  {sig['normalized']}")
    fixes = store.fixes_for(sig["id"])
    if fixes:
        typer.echo(f"修法（{len(fixes)} 条）：")
        for i, fx in enumerate(fixes, 1):
            git = f" · git:{fx['git_head'][:7]}" if fx["git_head"] else ""
            typer.echo(f"  {i}. [{fmt_ts(fx['ts'])}{git}] {fx['note']}")
    else:
        typer.echo("修法：还没有。修好了记得 solve。")
    occs = store.occurrences_for(sig["id"])
    typer.echo(f"出现记录（最近 {len(occs)} 次）：")
    for o in occs:
        typer.echo(f"  [{fmt_ts(o['ts'])} · {o['project']}]")
        for ln in o["excerpt"].splitlines():
            typer.echo(f"    | {ln}")


@app.command("top")
def top(
    all_: bool = typer.Option(False, "--all", help="跨项目排行。"),
    limit: int = typer.Option(10, "--limit", "-n", min=1, help="最多几条。"),
) -> None:
    """高频错误排行（默认当前项目）。✓ = 已有修法，· = 还没有。"""
    store = _open_readonly_store()
    rows = store.top(project=None if all_ else detect_project(), limit=limit) if store else []
    if not rows:
        typer.echo("errbook: 错题本还是空的。")
        return
    for r in rows:
        mark = "✓" if r["fix_count"] else "·"
        typer.echo(
            f"{r['scope_count']:>4}× {mark} sig {r['id']} · {r['tool']}"
            f" · 最近 {fmt_ts(r['last_seen'])}"
        )
        typer.echo(f"       {r['normalized'][:100]}")


@app.command("forget")
def forget(sig_id: str = typer.Argument(..., help="签名 ID，可只写前缀。")) -> None:
    """删除一个签名（连同出现记录与修法）。错入库也要能出库。"""
    store = Store()
    sig = _resolve_sig(store, sig_id)
    store.forget(sig["id"])
    typer.echo(
        f"errbook: 已删除 sig {sig['id']}（{sig['tool']}，出现 {sig['count']} 次）"
        "及其修法与出现记录。"
    )


def main() -> None:
    app()


if __name__ == "__main__":
    main()
