# errbook 的 ZCode 插件

本目录把仓库里的 agent 技能打包成 ZCode 插件，并把本仓库变成一个
ZCode 插件市场——任何人都可以直接添加本仓库来安装 errbook 技能。

## 结构

```
plugins/
├── marketplace.json          # 市场目录（name: errbook-market）
└── errbook/                  # 插件源（name: errbook, version 与主包一致）
    ├── .zcode-plugin/plugin.json
    └── skills/errbook/SKILL.md
```

## 发布时同步

`plugins/errbook/skills/errbook/SKILL.md` 是 `skills/errbook/SKILL.md`
的副本。改了技能内容后，发布前记得：

```bash
cp skills/errbook/SKILL.md plugins/errbook/skills/errbook/SKILL.md
```

并同步更新 `plugins/errbook/.zcode-plugin/plugin.json` 与
`plugins/marketplace.json` 里的 version / description。

## 安装（ZCode 桌面端）

1. **插件市场 → 添加 → 添加插件市场**，粘贴本仓库目录
   （或 clone 后的 `plugins/` 目录路径）。
2. **个人 → errbook-market → errbook → 安装**。
3. 安装后在输入框的技能选择器里选 errbook，然后直接说
   "又报错了"试试——agent 会按 SKILL.md 的循环走
   （失败 → check → 读历史 → 修 → solve）。

前置条件：本机已安装 errbook CLI（`pip install .`，见仓库根 README）。
