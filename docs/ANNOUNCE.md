# errbook 发布公告稿（v0.1.1）

> 用途：供发布到 V2EX / 掘金 / 知乎 / Linux.do / Reddit r/commandline 等社区。
> 发布前可按平台习惯增删，代码块和演示输出都是真实跑出来的，可以直接用。

---

# errbook · 给构建错误建一本带记忆的错题本

一句话：**错误按签名归档、修复方法跟着错误走，同一个坑第二次出现时，
第一句话告诉你"上次怎么好的"。**

## 痛点

同一个编译错误反复撞墙，根因不是能力，是修复知识没有留存结构——
散落在三个月前的聊天会话、临时文件、甚至记忆里。ChatGPT/agent 时代的
会话更是用完即弃：上次 agent 怎么帮你修的，这次它一无所知。

## 长什么样

用 `errbook run --` 包装任意构建命令，输出和退出码**原样透传**
（可以无脑替换原命令），错误自动入库：

```console
$ errbook run -- cmake -S . -B build
CMake Error at C:/share/cmake-3.31/Modules/FindPackageHandleStandardArgs.cmake:233 (message):
  Could NOT find GTest (missing: GTEST_LIBRARY GTEST_INCLUDE_DIR
  GTEST_MAIN_LIBRARY)
...
errbook: 已入库 1 条错误（新增 1 · 已知 0）
  + sig 93d867068627 · cmake · 新增
```

修好后记录一句（灵魂步骤）：

```console
$ errbook solve 93d867068627 "装了 GTest 并设置 CMAKE_PREFIX_PATH"
errbook: 已记录修法（git:1a2b3c4） —— sig 93d867068627 · cmake
```

下次再撞——**换目录、换行号、换数值都算同一个坑**：

```console
$ errbook run -- cmake -S . -B build
CMake Error at ...
errbook: 已入库 1 条错误（新增 0 · 已知 1）
  = sig 93d867068627 · cmake · 第 2 次
━━━━━━ errbook · 这错你修过 ━━━━━━
sig 93d867068627 · cmake · 历史出现 2 次（首次 2026-10-31 01:22）
上次怎么好的：
  1. [2026-10-31 01:23] 装了 GTest 并设置 CMAKE_PREFIX_PATH
本次摘录：
  | CMake Error at ...
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

## 技术核心：签名

签名 = (tool, 归一化哈希)。归一化剥掉路径（保留文件名）、行号、
十六进制地址、时间戳、PID、具体数值（`Tried to allocate 2.50 GiB` →
`Tried to allocate N`），保留错误类别 + 符号名 + 消息骨架；
`C2065`、`E0425`、`LNK2019`、`ERR_*` 这类错误代码原样保留。

8+1 种内置提取器（python-traceback / cmake / ninja / msvc / gcc-clang /
node / cargo / cuda-oom + generic 兜底），认领制去重：torch 的 OOM
traceback 记成显存坑而不是普通 traceback；ninja 的 FAILED 块把位置
让给里面的编译器错误。**归一化没把握的存原文并如实标 fuzzy**，
`check` 默认不出 fuzzy——不假装匹配得准。

## 设计立场（三条，不许破）

1. **纯本地、零网络**。错误摘录天然含源码、路径、密钥——永不上传；
   入库前自动截断（首尾各 20 行）+ 脱敏（`sk-…`、`ghp_…`、JWT、
   `KEY: value` 形态、长随机串打码）。
2. **签名诚实**。能归一的才归一，归不了的存原文并如实标 fuzzy。
3. **Agent 原生但人优先**。每个命令人都能直接用；agent 通过 SKILL.md
   接同一套命令。我们用 agent 会话实测过完整闭环：agent 撞到历史错误
   时直接复用修法，修复时间从"排查"变成"确认"（会话记录在 docs/ 里）。

## 安装

```bash
git clone https://github.com/HarryHeYu/errbook && cd errbook && pip install .
```

Python 3.9+，除 CLI 框架外零第三方运行时依赖（SQLite + FTS5 单文件存储，
Windows 老 Python 没有 FTS5 也能用，检索自动退化）。

## 给 agent 用户

把仓库里的 `skills/errbook/SKILL.md` 放进你的 agent 技能目录即可；
ZCode 用户可以直接把本仓库添加为插件市场（`plugins/marketplace.json`），
安装 errbook 技能。SKILL 固化的循环：**失败 → check → 读历史 → 修 → solve**。

## 边界（明确不做）

全局输出拦截、目录监听、编辑器/CI 集成、自动修复建议（那是 agent 的活，
errbook 只负责记忆）、多机同步。

---

GitHub：https://github.com/HarryHeYu/errbook （觉得有用的话点个 Star ⭐）
