# errbook · 构建错误错题本

> 给构建错误建一本带记忆的错题本——错误按签名归档、修复方法跟着错误走，
> 同一个坑第二次出现时第一句话告诉你"上次怎么好的"。

**核心信念：编译错误的修复过程不该是一次性消费，学习曲线不该是遗忘曲线。**

[English](README.md)

## 为什么

同一个错误反复撞墙的根因不是能力，是**修复知识没有留存结构**：散落在
三个月前的聊天会话、临时文件、甚至记忆里。errbook 把它变成结构化资产：

```
错误出现 → 提取 → 归一化签名 → 入库
   ↑                              │ 修复后
   │                              ▼
命中 → "这错你 X 月 X 日修过：<方法>" ← solve 记录
```

## 设计立场（三条，不许破）

1. **纯本地、零网络**。错误摘录天然含源码、路径、密钥——永不上传。
   FTS 全文检索走 SQLite，不引入任何服务。
2. **签名诚实**。能归一的才归一，归不了的存原文并如实标注 `fuzzy`，
   不假装智能匹配。
3. **Agent 原生但人优先**。CLI 每个命令人都能直接用；agent 通过
   [skills/errbook/SKILL.md](skills/errbook/SKILL.md) 接入同一套命令，
   不存在第二套逻辑。

## 安装

需要 Python 3.9+。

```bash
pip install errbook        # 或 pipx install errbook / uv tool install errbook
```

## 快速上手

用包装器跑任意构建/运行命令——输出与退出码原样透传，可以无脑替换原命令：

```console
$ errbook run -- cmake -S . -B build
CMake Error at C:/.../FindPackageHandleStandardArgs.cmake:233 (message):
  Could NOT find GTest (missing: GTEST_LIBRARY GTEST_INCLUDE_DIR)
...
errbook: 已入库 1 条错误（新增 1 · 已知 0）
$ echo $?
1
```

修好之后记下怎么好的（灵魂步骤，漏了等于白修）：

```console
$ errbook solve 93d867068627 "装了 GTest 并设置 CMAKE_PREFIX_PATH"
errbook: 已记录修法（git:1a2b3c4） —— sig 93d867068627 · cmake
```

下次再撞同一个坑——哪怕换目录、换行号、换数值——它还记得：

```console
$ errbook run -- cmake -S . -B build
CMake Error at ...
errbook: 已入库 1 条错误（新增 0 · 已知 1）
━━━━━━ errbook · 这错你修过 ━━━━━━
sig 93d867068627 · cmake · 历史出现 2 次（首次 2026-10-31 01:22）
上次怎么好的：
  1. [2026-10-31 01:23] 装了 GTest 并设置 CMAKE_PREFIX_PATH
本次摘录：
  | CMake Error at ...
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

错误来自包装不了的场景（比如远程 CI 日志）？直接喂进去：

```bash
errbook add --file ci-log.txt        # 或 cat ci-log.txt | errbook add
errbook check --file ci-log.txt      # 查历史，退出码恒为 0
```

## 命令一览

| 命令 | 用途 |
|---|---|
| `errbook run -- <cmd>` | 包装构建命令：透传 + 捕获入库 + 命中提醒。安全的默认用法。 |
| `errbook check [--file <log>]` | 拿一段错误文本查历史。退出码恒为 0——信息附加器，不是门禁。 |
| `errbook solve <sig-id> "<怎么好的>"` | 记录修法（在仓库内自动附记 git HEAD）。多次 solve 追加成列表（不同根因）。 |
| `errbook add [--file <log>]` | 手动/agent 粘贴一段错误文本入库。 |
| `errbook search <关键词>` | FTS 全文搜错误与修法（中文子串可以）。 |
| `errbook show <sig-id>` | 看完整档案：归一化签名、修法列表、出现记录。 |
| `errbook top [--all]` | 高频错误排行（默认当前项目）。 |
| `errbook forget <sig-id>` | 删掉某个签名（连同修法与出现记录）。错入库也要能出库。 |

签名 ID 支持只写前缀；前缀有歧义时会列出候选并拒绝执行。

## 签名是怎么工作的

- **提取器**（每种工具一个，v0.1 内置）：`python-traceback`（含链式异常、
  pytest E 行、裸 SyntaxError 块）、`cmake`、`ninja`、`msvc`（error Cxxxx /
  LNKxxxx）、`gcc-clang`（含 undefined reference）、`node`/npm、`cargo`
  （rustc E 码）、`cuda-oom`，外加 `generic` 兜底（未认领的错误行 +
  多行重复模式去噪）。注册表按认领制工作：越具体的越先认领——torch 的
  OOM traceback 记成显存坑而不是普通 traceback；ninja 的 `FAILED:` 块
  会把位置让给里面的编译器错误。
- **归一化**剥离路径（保留文件名）、行号、十六进制地址、时间戳、PID、
  具体数值（`Tried to allocate 2.50 GiB` → `Tried to allocate N`），
  保留错误类别 + 函数/符号名 + 消息骨架；`C2065`、`E0425`、`LNK2019`、
  `ERR_*` 等错误代码原样保留，不会被当数值剥掉。
- **签名 = (tool, 归一化哈希)**。原文摘录始终保留（首尾截断），命中时
  与历史修法并排展示，由人确认是否同款。
- 归一化没把握的（比如内含未知输出的 ninja FAILED 块）存原文并标
  `fuzzy`；`check` 默认不出 fuzzy 命中，`--fuzzy` 才看。

## 存储与隐私

- SQLite 单文件（stdlib `sqlite3` + FTS5，运行时零第三方依赖，
  CLI 体验仅用 `typer`/`rich`）。表：`signatures` / `occurrences` /
  `fixes` / `projects`。
- 默认位置 `~/.errbook/errbook.db`，环境变量 `ERRBOOK_DB` 可覆盖。
- 摘录入库前先截断（首尾各 20 行）并**自动脱敏**：已知前缀的
  token/密钥（`sk-…`、`ghp_…`、`AKIA…`、JWT、`Bearer …`）、
  `KEY: value` 形态、长随机 hex/base64 串一律打码。纯本地工具，
  但错题本本身也不该存密钥。
- 多项目：occurrence 带 project（git remote 的仓库名，仓库外则用目录名）。
  查询默认当前项目，`--all` 跨项目。

## 接入编码 agent

把 `skills/errbook/SKILL.md` 放进 agent 的 skill 目录。skill 固化了
循环：**失败 → check → 读历史 → 修 → solve**。solve 是灵魂步骤，
skill 里标了强制。

## 开发

```bash
git clone https://github.com/HarryHeYu/errbook
cd errbook
python -m venv .venv
.venv/Scripts/pip install -e ".[dev]"     # POSIX: .venv/bin/pip
.venv/Scripts/python -m pytest
```

测试矩阵自带 48 个真实样本（`tests/fixtures/`）——每个提取器至少 5 个，
外加跨环境变体组，必须折叠到同一签名。

## 边界（v0.1 明确不做）

全局系统级输出拦截、目录/日志监听、编辑器与 CI 集成、错误自动修复建议
（那是 agent 的活，errbook 只负责记忆）、多机同步。

## 许可证

尚未选择——见仓库后续更新。
