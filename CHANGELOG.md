# Changelog

本项目的所有显著变更记录于此。格式参考 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)。

## [0.1.1] - 2026-10-31

评审修复轮：四路独立评审（任务书合规 / 代码质量 / 黑盒实测 / 测试与文档审查）发现的问题全部处置。

### Fixed
- **签名一致性（P1）**：脱敏下沉到 `extract_all` 源头单点化——修复含密钥/长哈希的错误
  "记了却永远查不中"的不对称（record 与 find_hits 签名输入现在必然一致，展示层随之脱敏）。
- **无 FTS5 环境可用了（P1）**：Windows 官方 CPython ≤3.10 没有 SQLite FTS5，
  原先装上即坏；现在检索自动退化为 LIKE，`requires-python >=3.9` 重新成立。
- `errbook run -- 不存在的命令`：由裸 traceback 改为干净报错 + 退出码 127。
- cmake 提取器匹配真实措辞 `CMake Generate step failed. ...`（原样本失真掩盖了缺口）。

### Changed
- Windows 相对反斜杠路径归一（`src\main.cpp` → `main.cpp`），同一错误跨路径写法同一签名。
- UTF-16（PowerShell 重定向）BOM 日志探测；GBK 显式 cp936 尝试，跨机器可测。
- SQLite：WAL + `timeout=30`；查询型命令（check/search/top）不建库；提醒阈值按项目内出现次数判定。
- generic 提取器认领裸异常行（`ValueError:` / `NullPointerException:` 等）；gcc 拒绝纯数字伪路径；
  cargo 裸 `error:` 无佐证时如实标 fuzzy；search 保留 FTS 相关性排序；FTS 摘录去重防膨胀；
  POSIX 信号退出码按 128+N 透传。
- `add` / `check` 新增 `--raw`：远程 CI 日志等提取器认不出的格式，整段存/查为一个 fuzzy 签名（两侧对称）。

### Added
- GitHub Actions CI（ubuntu + windows × Python 3.9–3.14）。
- ZCode 插件与仓库内插件市场（`plugins/`），可直接把本仓库添加为插件市场。

### Tests
- 131 项（+20）：CLI 负路径、`--raw`/`--fuzzy`、FTS 降级、redact 对称回归钉、
  负样本 fixtures（warning / 无害输出必须保持沉默）、UTF-16 与跨平台 GBK。

## [0.1.0] - 2026-10-31

首个版本。

### Added
- 错误签名核心：归一化（剥路径保留文件名、行号/数值/时间戳/PID/hex 剥离，
  C2065 / E0425 / LNK2019 / ERR_* 等错误代码保留）+ 稳定哈希；签名 = (tool, norm_hash)。
- 提取器注册表（认领制）：python-traceback（链式异常 / pytest E 行 / 裸 SyntaxError）、
  cmake、ninja、msvc、gcc-clang、node/npm、cargo、cuda-oom、generic 兜底。
- SQLite 单文件存储（FTS5 trigram）+ 四表（signatures / occurrences / fixes / projects），
  多项目隔离（`--all` 跨项目），摘录首尾截断 + 自动脱敏。
- CLI：`run --`（透传 + 捕获 + 提醒）、`add`、`solve`（自动附记 git HEAD）、
  `check`（退出码恒 0）、`search`、`show`、`top`、`forget`。
- agent 接入：`skills/errbook/SKILL.md`（失败 → check → 读历史 → 修 → solve 循环）。
- 54 个真实样本的归一化测试矩阵 + E2E 验收（真实 cmake 错误闭环、agent 自主闭环记录见 docs/）。
