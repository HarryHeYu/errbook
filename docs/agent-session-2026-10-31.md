# errbook agent 会话验证记录（2026-10-31 · M3 验收）

任务书 M3 要求：SKILL.md 写完后，用**真实 agent 会话**验证 agent 能自主完成
「失败 → 查 → 修 → solve」闭环。以下是会话存档。

## 验证环境

- 模拟项目：`.tmp/agent-sim/`（`pipeline.py` + `importer.py` + `data.txt`，
  故意埋了两个 bug：包名拼错的 `import jsons`；`data.txt` 里 `5,0` 导致的除零）。
- 预埋历史：运行一次坏脚本让 `ModuleNotFoundError` 入库，并挂上一条
  solve 记录（"上周修过：包名写错，应为 json"），模拟"这个坑以前撞过"。
- 数据库：`ERRBOOK_DB=E:/code/errbook/.tmp/agent-sim/agent.db`（仓库内，不碰家目录）。
- 子 agent 收到的唯一指令：读 `skills/errbook/SKILL.md` 并按核心循环，
  把 `python pipeline.py` 修到退出码 0。无人为逐步引导。

## 会话存档（子 agent 原始回复）

### 1. 会话流程（按时间）

**Step 0 · 准备**
读了 `E:\code\errbook\skills\errbook\SKILL.md`，确认核心循环：run 包装 → 命中读历史 → 修 → solve。
扫了一遍项目文件：`pipeline.py`（load/transform/main）、`importer.py`（`import jsons`）、`data.txt`（三行数据，其中一行 `5,0`）。

**Step 1 · 第一次失败运行**

```
ERRBOOK_DB=... errbook run -- python pipeline.py
```

输出：`ModuleNotFoundError: No module named 'jsons'`（importer.py 第 1 行），EXIT=1。
errbook 输出 `已入库 1 条错误（新增 0 · 已知 1）`，并弹出提醒块（见第 2 节）。

**Step 2 · 复用历史修法**
对照摘录与 `importer.py`，确认同款：第 1 行 `import jsons`、第 4 行 `jsons.dumps`。
修改 `importer.py`：`import jsons` → `import json`，`jsons.dumps(...)` → `json.dumps(...)`。

**Step 3 · solve 记录 1**

```
errbook solve afc1a010e07e "importer.py 里 import jsons 是包名写错，改为 import json 并把
jsons.dumps 改成 json.dumps（标准库，无需装包）"
```

输出：`已记录修法（git:c22e626） —— sig afc1a010e07e · python-traceback`。

**Step 4 · 第二次失败运行**
`errbook run -- python pipeline.py`
输出：`ZeroDivisionError: division by zero`（pipeline.py 第 16 行），EXIT=1。
errbook 输出 `已入库 1 条错误（新增 1 · 已知 0）`，**无提醒块，未命中**。

**Step 5 · 正常排查修复**
根因是 `data.txt` 里的 `5,0` 行。选择修代码而不是改输入数据（数据管线应对脏数据健壮）：
在 `transform()` 里 append 前插入 `if int(den) == 0: continue`（跳过分母为 0 的无效行）。

**Step 6 · 取 sig-id**
这次 `run` 对新错误没有显示 sig-id，改用 `errbook search ZeroDivision` 拿到
`sig 690dd0c93e1e · python-traceback · 出现 1 次`。

**Step 7 · solve 记录 2**

```
errbook solve 690dd0c93e1e "data.txt 里有 5,0 这种分母为 0 的行，pipeline.py 的 transform
除零崩溃；在 transform 里加 if int(den) == 0: continue 跳过无效行"
```

### 2. 命中历史的那次

历史修法帮我把排查压到了零：修法一句话说清了根因（包名写错，应为标准库 `json`）
和动作（先核对包名再装包），与本次摘录的文件、行号、模块名完全一致，
我核对后直接照做，没有走"查这个包是什么、要不要 pip install"的弯路。
这正是错题本该有的效果。

### 3. 自主判断（子 agent 原话）

- **有用的**：`errbook run --` 包装器是全场最佳：一条命令同时拿到透传输出、
  退出码、自动入库和历史提醒，第一次失败就命中，省掉单独 check 的步骤。
  提醒块信息密度高：sig、出现次数、首次时间、修法原文、本次摘录并排，
  判断"是否同款"所需材料齐全。solve 即时回显确认（含 git 标注），闭环感明确。
- **没用/别扭的**：**新错误拿不到 sig-id**：run 对新增错误只打印 `新增 1 · 已知 0`，
  不给 sig-id，而 SKILL 声称"sig-id 在 check/run/add 的输出里"。我被迫多跑一条
  `errbook search` 才拿到，这是整个流程里最明显的断点——solve 是灵魂步骤，
  入口却不顺。小怪癖：solve 自动附记的 `git:c22e626` 取自外层 errbook 仓库的
  HEAD，对 `.tmp` 里的模拟项目来说指向了无关仓库。

### 4. 最终验证

`python pipeline.py` → `mean = 0.625`，EXIT=0。
共修复 2 个错误：`jsons` 拼写错（**命中历史，复用修法**）、transform 除零崩溃
（**未命中，自主修复**）；两个签名均已 solve 入库（`afc1a010e07e`、`690dd0c93e1e`）。

## 验收结论与改进跟进

| 结论 | 说明 |
|---|---|
| 闭环 ✅ | agent 无人为引导，自主完成 失败→查→修→solve，两轮循环 |
| 命中历史 ✅ | 提醒块一次命中，agent 复用修法直接修复，未走弯路 |
| 未命中路径 ✅ | 正常排查 + solve 补记，签名随后可被复用 |
| 反馈已修 ✅ | run 入库摘要现在逐条列出 sig-id（`+ sig … 新增 / = sig … 第 N 次`），
  solve 入口不再断；配套测试 `test_run_records_then_second_run_reminds` |
| 反馈已知 | `git:` 标注取所在 git 仓库 HEAD，是任务书 2.3 的设计行为
  （"可选自动捕获当前 git HEAD（在仓库内时）"），对模拟项目属预期噪音 |
