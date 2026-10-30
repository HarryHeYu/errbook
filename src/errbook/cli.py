"""errbook 命令行（Typer）。人能直接用；agent 通过 SKILL.md 接同一套命令，
不存在第二套逻辑。"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Optional

import typer

from . import __version__
from .capture import decode_output, run_wrapped
from .check import check_text
from .extract import extract_all
from .project import detect_project, git_head
from .store import AmbiguousSig, SigNotFound, Store, fmt_ts

# Windows 控制台编码兜底：打印别的终端贴进来的字符不炸
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(errors="replace")

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

    rc, out, err = run_wrapped(cmd)
    combined = out + "\n" + err
    extractions = extract_all(combined) if combined.strip() else []
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
        blocks, _ = check_text(store, combined, project=project, extractions=extractions)
        if blocks:
            typer.echo(blocks, err=True)
    raise typer.Exit(rc)


@app.command("add")
def add(
    text: Optional[str] = typer.Argument(None, help="错误文本；也可用 --file 或管道 stdin。"),
    file: Optional[Path] = typer.Option(None, "--file", "-f", help="从文件读取错误文本（自动探测编码）。"),
) -> None:
    """手动/agent 粘贴一段错误文本入库（错误来自无法包装的场景，如远程 CI 日志）。"""
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

    extractions = extract_all(body)
    if not extractions:
        typer.echo("errbook: 未识别到错误特征，未入库（贴错误本身比贴整段日志更准）。")
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
) -> None:
    """读一段错误文本（stdin 或 --file），命中历史时输出提醒块。退出码恒为 0。"""
    if file is not None:
        if not file.exists():
            typer.secho(f"errbook: 文件不存在：{file}", fg=typer.colors.RED, err=True)
            raise typer.Exit(2)
        body = decode_output(file.read_bytes())
    elif not sys.stdin.isatty():
        body = decode_output(sys.stdin.buffer.read())
    else:
        raise typer.Exit(0)  # 没输入也安静通过——信息附加器，绝不挡路

    blocks, _ = check_text(
        Store(),
        body,
        project=None if all_ else detect_project(),
        include_fuzzy=fuzzy,
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
    rows = Store().search(query, project=None if all_ else detect_project(), limit=limit)
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


def main() -> None:
    app()


if __name__ == "__main__":
    main()
