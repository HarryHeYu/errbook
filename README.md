# errbook · A mistake notebook for build errors

[![CI](https://github.com/HarryHeYu/errbook/actions/workflows/ci.yml/badge.svg)](https://github.com/HarryHeYu/errbook/actions/workflows/ci.yml)

> Give your build errors a memory. Errors are archived by stable signature,
> fixes travel with the error — and the next time you hit the same wall,
> the first line tells you *how you got over it last time*.

**Core belief: fixing a compiler error should not be a one-shot consumption.
The learning curve should not be a forgetting curve.**

[中文文档](README.zh-CN.md)

## Why

The root cause of hitting the same error over and over is not skill — it's
that **fix knowledge has no persistent structure**. It scatters across
chat sessions from three months ago, temp files, and your own memory.
errbook turns it into a structured asset:

```
error appears → extract → normalize → signature → archive
     ↑                                            │ after fixing
     │                                            ▼
hit → "you fixed this on Aug 12: <method>"  ← solve record
```

## Design stance (three rules, non-negotiable)

1. **Pure local, zero network.** Error excerpts naturally contain source
   code, paths and secrets — nothing ever leaves your machine. Full-text
   search runs on SQLite FTS5; no services involved.
2. **Honest signatures.** Normalize only what can be normalized reliably.
   Everything else is stored raw and honestly flagged `fuzzy`. No fake
   smart matching.
3. **Agent-native, human-first.** Every command works directly for humans;
   agents plug into the *same* commands via [skills/errbook/SKILL.md](skills/errbook/SKILL.md).
   There is no second logic path.

## Install

Requires Python 3.9+ (on Windows, official CPython 3.9/3.10 without SQLite FTS5
is supported too — search falls back to `LIKE`).

Not yet published to PyPI — install from source for now:

```bash
git clone https://github.com/HarryHeYu/errbook
cd errbook
pip install .
# or: pipx install .
```

## Quickstart

Wrap any build/run command — output and exit code pass through untouched,
so you can blindly replace your original command:

```console
$ errbook run -- cmake -S . -B build
CMake Error at C:/.../FindPackageHandleStandardArgs.cmake:233 (message):
  Could NOT find GTest (missing: GTEST_LIBRARY GTEST_INCLUDE_DIR)
...
errbook: 已入库 1 条错误（新增 1 · 已知 0）
$ echo $?
1
```

Record how it got fixed (the soul step — skipping it wastes the fix):

```console
$ errbook solve 93d867068627 "installed GTest; added CMAKE_PREFIX_PATH"
errbook: 已记录修法（git:1a2b3c4） —— sig 93d867068627 · cmake
```

Next time you hit the same error — even from a different directory,
with different line numbers and values — errbook remembers:

```console
$ errbook run -- cmake -S . -B build
CMake Error at ...
errbook: 已入库 1 条错误（新增 0 · 已知 1）
  = sig 93d867068627 · cmake · 第 2 次
━━━━━━ errbook · 这错你修过 ━━━━━━
sig 93d867068627 · cmake · 历史出现 2 次（首次 2026-10-31 01:22）
上次怎么好的：
  1. [2026-10-31 01:23] installed GTest; added CMAKE_PREFIX_PATH
本次摘录：
  | CMake Error at ...
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

Reminders appear when a signature **has a recorded fix**, or has been **seen
twice or more without one**. errbook's own notices always go to *stderr*
after the child's output — stdout stays byte-for-byte clean.

Got an error from somewhere unwrappable (a remote CI log)? Paste it in —
with `--raw` if the format is too exotic for the extractors:

```bash
errbook add --file ci-log.txt          # or: cat ci-log.txt | errbook add
errbook add --raw --file ci-log.txt    # store as one fuzzy signature, no parsing
errbook check --file ci-log.txt        # check history, exit code always 0
errbook check --raw --file ci-log.txt  # match against raw signatures too
```

## Commands

| Command | Purpose |
|---|---|
| `errbook run -- <cmd>` | Wrap a build command: passthrough + capture + reminders. The safe default. |
| `errbook check [--file <log>]` | Check a piece of error text against history. Reminds on signatures with a fix, or seen ≥2 times without one. Exit code is always 0 (only `--file` pointing to a missing file returns 2) — it's an information adder, not a gate. |
| `errbook solve <sig-id> "<how>"` | Record the fix (auto-attaches git HEAD when inside a repo). Multiple solves = multiple root causes. |
| `errbook add [--file <log>] [--raw]` | Manually paste an error text into the notebook. `--raw` stores the whole text as one fuzzy signature without parsing. |
| `errbook search <query>` | FTS full-text search over excerpts and fixes (CJK substrings work). |
| `errbook show <sig-id>` | Full dossier: normalized signature, fixes, occurrences. |
| `errbook top [--all]` | High-frequency error ranking (current project by default). |
| `errbook forget <sig-id>` | Delete a signature with its fixes and occurrences. |

Sig IDs can be written as prefixes; `errbook` complains loudly if a prefix
is ambiguous. Read-only commands (`check`/`search`/`top`) never create the
database — with no notebook yet they simply stay quiet.

**Projects**: a project is a git repository (named after its `origin`
remote); every subdirectory inside it shares the same project. Outside a
repo, the directory name is used. Queries default to the current project;
`--all` spans projects.

## How signatures work

- **Extractors** (one per tool, v0.1): `python-traceback` (incl. chained
  exceptions, pytest `E` lines, bare SyntaxError blocks), `cmake`, `ninja`,
  `msvc` (error Cxxxx / LNKxxxx), `gcc-clang` (incl. `undefined reference`),
  `node` / npm, `cargo` (rustc E-codes), `cuda-oom`, plus a `generic`
  fallback (unclaimed error lines + repeated-line denoising).
  The registry is claim-based: the most specific extractor wins, so a
  torch OOM inside a Python traceback is remembered as an OOM, not a
  generic traceback, and a ninja `FAILED:` block defers to the compiler
  error inside it.
- **Normalization** strips paths (keeping the file name), line/col numbers,
  hex addresses, timestamps, PIDs and raw values (`Tried to allocate
  2.50 GiB` → `Tried to allocate N`), while keeping the error category,
  symbol names and the message skeleton — and error codes like `C2065`,
  `E0425`, `LNK2019`, `ERR_*` are preserved verbatim.
- **Signature = (tool, normalized hash)**. The raw excerpt is always kept
  (head/tail truncated), shown side by side with historical fixes so a
  human confirms it's the same pit.
- Non-normalizable stuff (e.g. a `ninja: FAILED:` block with unknown inner
  output) is stored raw and flagged `fuzzy`; `check` hides fuzzy hits
  unless `--fuzzy`.

## Storage & privacy

- Single SQLite file (stdlib `sqlite3`; FTS5 full-text search with graceful
  `LIKE` fallback when FTS5 is unavailable). Zero runtime dependencies
  beyond the CLI framework (`typer`/`rich`). Tables: `signatures`,
  `occurrences`, `fixes`, `projects`.
- Location: `~/.errbook/errbook.db` by default; set `ERRBOOK_DB` to override.
- Excerpts are truncated (head/tail 20 lines) and **auto-redacted** before
  storage: known token/key prefixes (`sk-…`, `ghp_…`, `AKIA…`, JWTs,
  `Bearer …`), `KEY: value` pairs, and long random hex/base64 runs are
  masked. This is a local-only tool, but the notebook itself shouldn't
  hold secrets either.
- Multi-project: occurrences carry a project name (git remote repo name,
  or the directory name outside a repo). Queries default to the current
  project; `--all` spans projects.

## Using with coding agents

Copy/symlink `skills/errbook/SKILL.md` into your agent's skill directory.
The skill encodes the loop: **fail → check → read history → fix → solve**.
`solve` is the soul step; the skill marks it mandatory.

**ZCode users**: this repository doubles as a plugin marketplace —
add the repo's `plugins/` directory via *Plugin Marketplace → Add*, then
install the `errbook` skill plugin (see [plugins/README.md](plugins/README.md)).

## Development

```bash
git clone https://github.com/HarryHeYu/errbook
cd errbook
python -m venv .venv
.venv/Scripts/pip install -e ".[dev]"     # POSIX: .venv/bin/pip
.venv/Scripts/python -m pytest
```

The test matrix ships 54 real-world samples under `tests/fixtures/` —
at least 5 per extractor plus cross-environment variant groups that must
collapse to the same signature, and negative samples (warnings, benign
output) that must stay out.

## Scope (v0.1 explicitly does NOT do)

System-wide output interception, directory/log watching, editor or CI
integrations, automatic fix suggestions (that's the agent's job — errbook
only remembers), multi-machine sync.

## License

Not yet chosen — see the repository for updates.
