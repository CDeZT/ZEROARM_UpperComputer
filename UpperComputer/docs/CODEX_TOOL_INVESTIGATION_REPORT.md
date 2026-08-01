# Codex 上位机开发工具调查方案 · 调查报告

调查日期：2026-08-01
执行阶段：第一阶段调查（只调查、不安装）已完成；**第二阶段（安装）已按用户确认逐步执行，见第 11 节执行记录**
方案来源：`/Users/wangzilin/Downloads/Codex_上位机开发工具调查方案.pdf`（27 页，作者 ChatGPT Canvas）

---

## 1. 当前项目与 Codex 环境

| 项 | 实测值 |
|---|---|
| 操作系统 | macOS（Apple Silicon），Windows 为最终发布目标 |
| Codex 形态 | ChatGPT 桌面 App（browser 构建 26.727.51351）+ 内置 Codex CLI `codex-cli 0.146.0-alpha.9.2` |
| 模型 | deepseek-v4-flash（deepseek provider，`~/.codex/config.toml`），reasoning effort=max |
| 上位机技术栈 | Python >=3.12,<3.14 + PySide6 6.8–6.10（**纯 Qt Widgets**，全仓 0 个 `.qml/.ui` 文件） |
| 构建/包管理 | uv（0.11.32）+ `uv.lock`；PyInstaller spec + Inno Setup 脚本 |
| 测试框架 | pytest + pytest-qt（offscreen）+ hypothesis；当前基线 mypy 通过，GUI 测试因 R15 未提交改动变红（见 6.3） |
| Git | `CDeZT/ZEROARM_UpperComputer`、`CDeZT/zero_arm_mcu`（GitHub） |
| 已启用 Plugins | visualize、browser（openai-bundled）；documents、pdf、presentations、spreadsheets、template-creator（openai-primary-runtime）；github（openai-curated-remote，含 gh-* skills） |
| 已安装但未启用 | computer-use（config 中 enabled=false） |
| 已配置 MCP | node_repl（启用）；computer-use（禁用） |
| 用户级 Skills 目录 | `~/.codex/skills/`（仅剩 `.system/`：imagegen、openai-docs、plugin-creator、review-agent、skill-creator、skill-installer） |
| 项目级 Skills | 无（仓库根无 `.agents/skills`） |
| 项目规范文件 | `UpperComputer/AGENTS.md`、`PROJECT_SPEC.yaml`、`docs/01~20` 全套 |

### 1.1 Codex 技能发现路径（官方手册核实）

来源：OpenAI Codex 官方手册（`developers.openai.com/plugins/concepts/skills.md`、`learn.chatgpt.com/docs/build-skills.md`，2026-08-01 抓取）。

| 作用域 | 位置 | 本项目现状 |
|---|---|---|
| REPO | `$CWD/.agents/skills`、`$CWD/../.agents/skills`、`$REPO_ROOT/.agents/skills` | 无，建议自建技能放这里 |
| USER | `$HOME/.agents/skills` | 无 |
| ADMIN | `/etc/codex/skills` | 无 |
| SYSTEM | Codex 内置 | `~/.codex/skills/.system`（本会话可见） |

要点：
- 技能采用 `SKILL.md`（`name` + `description` 必填），渐进式加载；隐式触发靠 description，显式用 `/skills` 或 `$skill`。
- 官方手册写 USER 作用域为 `~/.agents/skills`；`skill-installer` 脚本默认写入 `$CODEX_HOME/skills`（本机 `~/.codex/skills`）。两者在 App 中是否同时发现需**安装后实测**（本会话确认 SYSTEM 技能位于 `~/.codex/skills/.system`，但用户级路径以官方手册 `~/.agents/skills` 为准）。
- Codex 会自动检测技能变化；未出现则重启 Codex。
- 初始技能列表上下文预算约 2% 或 8000 字符，装太多会截断描述甚至省略技能。
- 插件：ChatGPT 桌面 App 与 Codex CLI 共用统一插件目录；App 内 Plugins 侧栏安装，CLI 用 `/plugins`；安装后需新会话生效。
- 技能禁用：`~/.codex/config.toml` 中 `[[skills.config]] path=... enabled=false`。

---

## 2. 候选审计总表

评分制（满分 100）：技术栈匹配 25 / Codex 原生兼容 15 / 代码质量提升 15 / UI/UX 提升 15 / 成熟度 10 / 安全可控 10 / 重复度 5（越高分越低）/ 上下文成本 5。
分类：85-100 强烈推荐 · 70-84 推荐 · 55-69 条件安装 · 40-54 只提取部分规则 · 0-39 不建议。

### 2.1 Qt 官方（TheQtCompanyRnD/agent-skills，main @ 71d6c10d，无正式 tag，BSD-3-Clause OR Qt Commercial）

| 候选 | 类型 | 版本 | 许可证 | 明确支持 Codex | 技术栈适配 | 实际作用 | 重叠/风险 | Token | 评分 | 结论 |
|---|---|---|---|---|---|---|---|---|---|---|
| qt-ui-design | Skill | 1.0 | BSD-3-Clause | 是（工具无关） | 高（Qt Widgets 通用设计/审查；部分 QML 风格内容不适用） | UI 规划、信息层级、布局、导航、动效时长、审计清单 | 与 emil/ui-ux 有理念重叠；纯文本无脚本 | 中 | **82** | **强烈推荐（唯一外部 UI 设计 skill）** |
| qt-qml | Skill | 1.1 | BSD-3-Clause | 是 | 无（0 个 QML 文件） | QML 编码规范 | 无 | 低 | 45 | 不建议（纯 Widgets） |
| qt-qml-review | Skill | 1.0 | BSD-3-Clause | 部分（Claude 风格并行 agent；Codex 可改编） | 无 | QML 审查（47+ 规则 + qmllint） | 无适用对象 | 低 | 46 | 不建议 |
| qt-cpp-review | Skill | 2.0 | BSD-3-Clause | 部分 | 无（上位机是 Python；MCU 是 C 非 Qt） | Qt C++ 审查（60+ 规则） | 无适用对象 | 低 | 42 | 不建议 |
| qt-qml-profiler | Skill | 1.0 | BSD-3-Clause | 是 | 无（仅 Qt Quick 2D） | qmlprofiler 分析 | 无适用对象 | 低 | 38 | 不建议 |
| qt-qml-test | Skill | 1.0 | BSD-3-Clause | 是 | 无 | 生成 tst_*.qml | 无 | 低 | 36 | 不建议 |
| qt-qml-test-run | Skill | 1.0 | BSD-3-Clause | 是 | 无（依赖 CMake+QML 工程） | 运行 QML 测试 | 无 | 低 | 34 | 不建议 |
| qt-cmake-project | Skill | 1.0.1 | BSD-3-Clause | 是 | 无（本项目无 CMake/Qt C++） | Qt6 CMake 工程 | 无 | 低 | 35 | 不建议 |
| qt-qml-docs | Skill | 1.0 | BSD-3-Clause | 是 | 无 | QML 文档生成 | 无 | 低 | 33 | 不建议 |
| qt-cpp-docs | Skill | 1.0 | BSD-3-Clause | 是 | 无 | C++ 文档生成 | 无 | 低 | 32 | 不建议 |
| qt-figma-token-extraction | Skill | 1.0 | BSD-3-Clause | 是 | 无（输出 QML Singleton；需 Figma MCP） | Figma token → QML | 无 | 低 | 40 | 不建议（条件：Figma+QML 才考虑） |
| qt-figma-component-generation | Skill | 1.0 | BSD-3-Clause | 是 | 无（依赖上者 + Qt Quick Controls 2） | Figma 组件 → QML | 无 | 低 | 35 | 不建议 |
| qt-documentation-mcp | MCP | 托管服务 | Qt 服务条款 | 是（官方给了 Codex App 接入步骤） | 中（PySide6 底层是 Qt Widgets/C++ API，类名一致；PySide6 文档覆盖**未确认**） | Qt 6.8.4/6.11.0 官方 API 检索（qt_documentation_search/read） | 只读 HTTPS；上下文按需 | 低 | **66** | **条件安装（推荐试装并实测 PySide6 覆盖）** |

Qt MCP 接入（官方 setup-manual.md）：Codex App Settings → MCP servers → Add Server → Streamable HTTP → `https://qt-docs-mcp.qt.io/mcp`。

### 2.2 PySide6 / PyQt6 专项

| 候选 | 来源/版本 | 许可证 | 明确支持 Codex | 技术栈适配 | 实际作用 | 重叠/风险 | Token | 评分 | 结论 |
|---|---|---|---|---|---|---|---|---|---|
| pyqt6-ui-development-rules | oimiragieo/agent-studio `.claude/skills/`，repo v3.2.0+ 活跃，**根目录无 LICENSE 文件** | 未确认 | 否（Claude Code 专属 frontmatter/hooks/commands/scripts；SKILL.md 本体可提取） | 中高（规则主题匹配：MVC/信号槽/QThread/QSS/布局/高 DPI；但示例是 PyQt6 命名） | 生产级 PyQt6 规则 | 与 `AGENTS.md` §6.2 高度重叠；PyQt6→PySide6 需改写；无许可证不可分发 | 低 | 52 | **不安装公共版，只提取适用规则，改写为项目自建 skill** |
| pyside6-qt-python（Bonnary video-editor-ai） | 社区聚合 | 未确认 | 未确认 | 中 | 视频编辑器场景 PySide6 配方 | 单一项目场景、维护证据不足 | 低 | 38 | 不建议 |
| py-gui（stevenke1981/python_skills） | 社区 | 未确认 | 未确认 | 中 | 多框架 GUI 提示 | 泛泛提示词包装 | 低 | 34 | 不建议 |
| building-qt-apps（quick-brown-foxxx） | 社区 | 未确认 | 未确认 | 中 | qasync 架构提示 | 场景单一 | 低 | 32 | 不建议 |
| pyqt6-ui-designer（aminechraibi） | 社区 | 未确认 | 否（Claude） | 中 | QSS/主题配方 + Context7 | Claude 向 | 低 | 36 | 不建议 |

社区结论：截至 2026-08-01 未找到维护良好、明确支持 Codex、值得直接安装的 PySide6 Widgets 公共技能；**自建 `pyside6-upper-computer` 是更优解**。

### 2.3 设计品味与设计系统

| 候选 | 来源/版本 | 许可证 | 明确支持 Codex | 技术栈适配 | 实际作用 | 重叠/风险 | Token | 评分 | 结论 |
|---|---|---|---|---|---|---|---|---|---|
| emil-design-eng | emilkowalski/skills main@70744e38（无 tag） | MIT | 是（SKILL.md 通用） | 低中（原则可迁移到 QPropertyAnimation/QEasingCurve；代码示例全是 CSS/Framer Motion） | UI 品味、动效决策框架（频率/时长/缓动/克制） | 与 qt-ui-design 动效部分重叠；web 代码不可直接用 | 中 | **61** | **条件安装（只装这一个；其余动画类不装）** |
| review-animations / improve-animations / find-animation-opportunities | 同上 | MIT | 是（disable-model-invocation） | 低 | 动画审查/审计（CSS 规则为主） | 与上重叠；Qt 需改写 | 中 | 52-58 | 条件/只提取原则 |
| animation-vocabulary | 同上 | MIT | 是 | 低 | web 动效术语表 | 无关 | 低 | 45 | 不建议 |
| apple-design | 同上 | MIT | 是 | 低中（弹簧/手势理念可迁移，代码是 web） | Apple 流体交互原则 | 与 emil 重叠 | 中 | 56 | 条件/只提取原则 |
| pick-ui-library | 同上 | MIT | 是 | 无（web 库选择器） | 给 web 选库 | 与 Qt 无关 | 低 | 15 | 不建议 |
| ui-ux-pro-max | nextlevelbuilder/ui-ux-pro-max-skill v2.9.0；npm CLI `ui-ux-pro-max-cli` v2.5.0 | MIT | 是（`uipro init --ai codex` 官方列出） | 中低（设计数据 84 风格/192 色板/字体/图表/UX 准则；支持栈 22 个但**无 Qt/PySide**） | 设计 Token、配色、字号、间距、图表选择、Dashboard 信息架构、Design System 生成器 | CLI 会写技能目录；Python 脚本需审计（克隆后 grep 未发现遥测）；与 qt-ui-design/emil 重叠 | 高（数据量大） | **61** | **条件安装（只做参考查询，禁止直接生成 web 风格代码）** |
| Anthropic frontend-design | anthropics/skills main@b29e7cf6 | Apache-2.0 | 是 | 低（web/CSS 专属） | 反模板美学、视觉方向、字体/构图 | 只可提取理念 | 中 | 53 | 只提取部分规则（不装） |
| Microsoft frontend-design-review | microsoft/skills main@4a2873fa（.github/skills/frontend-design-review） | MIT | 是（SKILL.md 通用） | 低（web 前端三支柱：洞察到行动/工艺/可信构建） | UI 审查方法 | Azure 仓库 WIP；web 向 | 中 | 51 | 只提取部分规则（不装） |

### 2.4 架构、审查、调试与 TDD

| 候选 | 来源/版本 | 许可证 | 明确支持 Codex | 技术栈适配 | 实际作用 | 重叠/风险 | Token | 评分 | 结论 |
|---|---|---|---|---|---|---|---|---|---|
| codebase-design | mattpocock/skills v1.1.0 | MIT | 是（纯 Markdown） | 高（深模块/接口/seam/adapter 词汇普适，正好可描述本项目的分层） | 架构词汇与原则 | 与自建架构 skill 可能重叠（可作为其内容来源） | 低 | **70** | **推荐** |
| domain-modeling | 同上 | MIT | 是 | 高 | 领域术语/词汇表/ADR（Device/Connection/Transport/Command/…） | 项目已有文档体系，可轻量采纳 | 低 | 64 | 条件（或并入自建 skill） |
| improve-codebase-architecture | 同上 | MIT | 部分（依赖 Claude `Explore` 子代理 + HTML 报告，Codex 需改编） | 高 | 架构“加深”机会扫描 | 与 codebase-design 配套 | 中 | 59 | 条件（改编后可用） |
| code-review | 同上 | MIT | 是（两轴并行审查：Standards+Spec；依赖 issue-tracker 文档） | 高（通用） | diff/PR 审查 | 与项目自身审查流程重叠；与 Qt 审查无冲突 | 中 | 65 | 条件（与自建 desktop-ui-review 二选一） |
| tdd | 同上 | MIT | 是 | 高（协议/CRC/状态机/校验非常适合） | 红绿循环纪律、seam 测试 | 项目已有良好测试文化，作纪律补充 | 低 | **67** | **推荐（可选）** |
| supercent code-review | supercent-io/skills-template | 未确认 | 未确认 | 中 | 8 步审查法 | 泛化、证据不足 | 低 | 44 | 不建议 |
| mistakenot code-review | Mistakenot 个人仓库 | 未确认 | 未确认 | 中 | 任务规划流审查 | 证据不足 | 低 | 40 | 不建议 |
| systematic-debugging | obra/superpowers v6.2.0 | MIT | 是（官方 Codex 插件市场亦有 Superpowers；本 SKILL.md 可独立复制） | 高（正好覆盖串口偶断/线程竞争/状态机错乱/UI 卡死） | 四阶段根因调查（Iron Law：无根因不修复） | 与项目“一次一单元”纪律互补 | 低 | **70** | **推荐** |
| plannotator | backnotprop/plannotator v0.9.3（npm 0.25.1） | MIT OR Apache-2.0 | 部分（Codex **实验性 Stop hook**，仅 macOS/Linux/WSL；Windows hooks 官方禁用） | 中 | 计划/HTML/PR 可视化批注，反馈回灌 agent | curl\|bash 安装、修改 Codex hooks 与 `~/.codex`、本地 web UI；需信任 | 中 | 48 | 暂不安装（等 hook 稳定/Windows 支持） |

### 2.5 Figma、Playwright、Windows 桌面自动化

| 候选 | 来源/版本 | 许可证 | 明确支持 Codex | 技术栈适配 | 实际作用 | 重叠/风险 | Token | 评分 | 结论 |
|---|---|---|---|---|---|---|---|---|---|
| Figma 官方插件 + figma-* 技能（curated：figma、figma-generate-design、figma-implement-design 等 8 个） | OpenAI 官方插件目录 / openai/skills .curated | 见插件条款 | 是 | 无（当前无 Figma 文件、无设计系统） | 设计稿→代码、token、组件 | 需 Figma 账号/授权读写 | 中 | 51 | 条件（建立设计系统后） |
| Playwright（MCP/CLI/curated 技能） | OpenAI 官方（/skills 可装 playwright、playwright-interactive；官方文档用于浏览器验证） | 开源 | 是 | 无（纯 Qt Widgets 无法用） | 浏览器 E2E/截图/console | 仅未来 Electron/Tauri/Web 时有用 | 中 | 43 | 不建议（Qt Widgets 不适用） |
| mcp-windows | sbroenne/mcp-windows v1.3.9（.NET 10） | MIT | 未声明（standalone MCP 可配任意客户端） | 中高（Windows 上位机 UIA 语义定位：按名称找按钮，DPI/多屏；Qt Widgets 标准控件可暴露 UIA，自定义绘制需截图回退） | Windows GUI 自动化：找窗口/点击/输入/截图 | 桌面级控制权限（必须限定只操作测试版上位机）；Windows-only | 中 | **55** | **条件安装（Windows 真机验收阶段；与 WinAppDriver 二选一）** |
| Servo MCP | npm `servo-mcp` | 未确认 | 未确认 | 中（macOS+Windows） | 截图/点击桌面 | 视觉为主、证据不足、稳定性未确认 | 中 | 36 | 不建议 |
| Qt 原生测试（Qt Test/Quick Test/Squish） | Qt 官方 | LGPL/商业 | 不适用 | QML 无；pytest-qt 已覆盖 Widgets | 确定性测试 | 项目已用 pytest-qt | 低 | 60（pytest-qt 已有） | 已满足，不新增 |
| WinAppDriver / Appium Windows | 微软/社区 | MIT | 不适用 | 中（Windows UIA） | Windows GUI 测试 | 与 mcp-windows 二选一 | 中 | 50 | 条件（Windows 阶段） |

### 2.6 其他 MCP

| 候选 | 来源/版本 | 许可证 | 明确支持 Codex | 适配 | 实际作用 | 重叠/风险 | Token | 评分 | 结论 |
|---|---|---|---|---|---|---|---|---|---|
| GitHub（App 插件已装：openai-curated-remote/github 0.1.8，gh-* skills） | OpenAI 官方 + GitHub MCP（github/github-mcp-server） | 官方 | 是 | 高（仓库在 GitHub） | PR/Issue/CI/Code Review | 默认只读即可；禁止自动 merge/push | 中 | 60 | 已满足；需要更多 API 时再评估独立 GitHub MCP |
| Context7 | upstash/context7；`ctx7 setup --codex` / 官方插件 | 开源 | 是（官方 Codex 文档页） | 中（PySide6/pyserial/qasync 等第三方文档） | 最新库文档检索 | 会写 `~/.codex/config.toml` + AGENTS.md + OAuth/API key；与 Qt MCP 重叠 | 中 | 47 | 条件（Qt MCP 无法覆盖 PySide6 时再装） |

### 2.7 Codex 官方基础能力（无需安装）

| 能力 | 结论 | 证据 |
|---|---|---|
| skill-installer | 已内置（SYSTEM）。可装 curated 技能，也可从任意 GitHub 仓库按路径安装；本调查中已实测成功安装/卸载 4 个技能 | `~/.codex/skills/.system/skill-installer/scripts/install-skill-from-github.py --repo <owner>/<repo> --path <path>`；官方手册 `$skill-installer` |
| skill-creator | 已内置。自建上位机技能用它生成骨架（`scripts/init_skill.py` + `quick_validate.py`） | `~/.codex/skills/.system/skill-creator`；官方手册 `$skill-creator` |
| plugin-creator | 已内置。仅当需要把多个技能/MCP/配置打包成插件时用；**本项目先用项目级技能，不创建插件** | `~/.codex/skills/.system/plugin-creator`（默认 `~/plugins`、个人 marketplace `~/.agents/plugins/marketplace.json`） |

---

## 3. 强烈推荐安装（需用户确认后执行）

| 工具 | 为什么 | 不装的损失 | 负责的层 | 触发方式 | 验证方式 |
|---|---|---|---|---|---|
| qt-ui-design | Qt 官方、BSD、活跃；是唯一覆盖“Qt 项目 UI 规划/审查”的外部技能 | UI 设计/审查缺少系统方法，容易凭直觉改界面 | UI/UX 规划与审查层 | 隐式（UI 设计/审查请求）+ 显式 `$qt-ui-design` | 让它审查 connection/dashboard 页，核对是否输出信息层级/操作流程/状态设计/高 DPI/键盘无障碍 |
| systematic-debugging | MIT、v6.2.0、独立 SKILL.md；正好覆盖串口偶断、线程竞争、状态机错乱、UI 卡死类问题 | 遇到诡异 bug 容易陷入“猜补丁”循环 | 调试方法论 | 隐式（bug/测试失败/异常行为） | 故意注入 Mock 丢帧/CRC 错误，确认它先做根因调查再改代码 |
| mattpocock codebase-design（或作为自建架构技能的内容源） | MIT、v1.1.0；深模块/接口/seam/adapter 词汇与当前分层完全契合 | 架构改进缺乏统一词汇，模块边界容易再次腐化 | 架构设计词汇层 | 隐式（模块设计/重构） | 让它用统一词汇描述 DeviceSession/Transport/Codec 边界，核对是否产出 seam 建议 |
| mattpocock tdd（可选） | MIT；协议/CRC/状态机/参数校验是 TDD 高价值区 | 复杂逻辑容易“先写实现后补测试” | 测试纪律 | 隐式（新协议/状态机/校验功能） | 对一个 V1 codec 新字段先写失败测试再实现 |
| qt-documentation-mcp | 官方托管、版本锁定（6.8.4/6.11.0）、Codex App 原生接入步骤；Qt Widgets API 名与 PySide6 一致 | Qt API 容易靠记忆写错（信号签名、枚举、重载） | 文档查询层 | 工具调用（qt_documentation_search/read） | 接入后搜索 `QThread`/`Signal`/`QSettings`，并**实测搜索 PySide6 是否命中**；不命中再上 Context7 |

## 4. 条件安装

| 工具 | 触发条件 |
|---|---|
| emil-design-eng | 只装这一个（品味/动效决策框架）；**Qt 落地时只迁移原则**（频率、时长 ≤300ms、缓动、克制），禁止照搬 CSS/Framer Motion 代码 |
| ui-ux-pro-max | 需要配色/字号/间距/图表/Dashboard 信息架构时作为**只读查询库**；禁止其直接产出 web 风格代码；CLI 安装前先审 `uipro init` 写入路径 |
| qt-documentation-mcp | 见 3；若实测不覆盖 PySide6，降级为“仅 Qt Widgets C++ 参考”或再加 Context7 |
| mattpocock domain-modeling / improve-codebase-architecture / code-review | 项目领域词汇表、架构扫描、PR 审查需要时；code-review 与自建 desktop-ui-review **二选一**；improve 需先在 Codex 下验证无 Claude 专属依赖 |
| mcp-windows | 只在 Windows 真机 GUI 自动化阶段；**必须限定窗口/进程只允许测试版上位机**，不点系统授权弹窗，与 WinAppDriver 二选一 |
| Context7 | 当 Qt MCP 无法覆盖 PySide6/pyserial 等第三方文档且需要实时文档时；安装会写 config + AGENTS.md，先备份 |
| Figma 官方插件 + figma-* 技能 | 建立 Figma 设计系统/需要设计稿→代码时；当前无 Figma 文件 → 不装 |
| Superpowers 官方插件（可选替代） | 若想要完整方法论插件，Codex App Plugins 目录搜索 Superpowers；但本项目**只建议取 systematic-debugging 单技能**，避免整套强制工作流 |

## 5. 不建议安装

| 工具 | 原因 |
|---|---|
| qt-qml、qt-qml-review、qt-qml-test、qt-qml-test-run、qt-qml-profiler、qt-qml-docs | 全仓 0 个 QML 文件，纯 Widgets |
| qt-cpp-review、qt-cpp-docs、qt-cmake-project | 上位机是 Python；MCU 是 C11 非 Qt；无 Qt CMake 工程 |
| qt-figma-token-extraction / qt-figma-component-generation | 输出 QML Singleton；需 Figma + Qt Quick Controls 2 |
| pyqt6-ui-development-rules（公共版） | PyQt6 命名、Claude Code 专属结构、**仓库无 LICENSE**、与 AGENTS.md §6.2 高度重复 → 改写为自建 |
| 社区 PySide6/PyQt6 技能（Bonnary、stevenke1981、quick-brown-foxxx、aminechraibi 等） | 单项目/泛提示词/无维护证据，不如自建 |
| Anthropic frontend-design、Microsoft frontend-design-review | web/CSS 专属；只提取“反模板、三支柱审查、任务可完成性”原则 |
| supercent / mistakenot code-review | 证据不足、无许可证确认；mattpocock code-review 已足够 |
| plannotator | Codex 支持依赖实验性 Stop hook（Windows 官方禁用），安装方式是 curl\|bash 且修改 hooks/config |
| Playwright（MCP/CLI） | 无法驱动 Qt Widgets；未来 Electron/Tauri/Web 再说 |
| Servo MCP | 稳定性与 Codex 兼容性证据不足，且与 mcp-windows 冲突 |
| ui-ux-pro-max 的 stack/gallery/CLI 全量 | 只需要 skill 目录本身（.claude/skills/ui-ux-pro-max） |

## 6. 最小推荐组合（确认后一次性落地）

```text
1 个 UI 设计        : qt-ui-design（外部唯一）
1 个 UI Taste       : emil-design-eng（仅原则）＋自建 upper-computer-ux 承载 Qt 落地规则
1 个架构            : 自建 upper-computer-architecture（内容源自 mattpocock codebase-design/domain-modeling）
1 个通用 Review     : 自建 desktop-ui-review（整合 qt-ui-design + emil + 工业上位机安全原则）；不装第二套通用 review
1 个框架专项 Review : 自建 pyside6-development（整合 pyqt6 规则适用部分 + AGENTS.md §6.2）
1 个调试            : systematic-debugging
1 个文档 MCP        : qt-documentation-mcp（试装；不足再 Context7）
1 个 UI 自动验证    : pytest-qt（已有）＋保留现有 GUI E2E；Windows 阶段条件加 mcp-windows
```

另外自建 `device-state-machine`（连接/重连/执行/超时/取消状态机审查）与 `protocol-contract`（V1 契约审查）。

## 7. 扩展组合（后续按需）

- 建立 Figma 设计系统 → Figma 官方插件 + figma-* 技能（Qt 侧只能提取 token 规范，不生成 QML）。
- 上位机迁移 Electron/Tauri/Web → Playwright。
- Windows 真机验收/GUI 自动化 → mcp-windows（限权）。
- 需要 PySide6/pyserial 等第三方实时文档 → Context7。
- 需要团队插件分发/多技能打包 → plugin-creator。
- 需要多 Agent 工作流/计划可视化 → 等 Codex hook 稳定后再评估 plannotator 或 Superpowers 完整插件。

## 8. 自建 Skills 建议（skill-creator 骨架，放仓库根 `.agents/skills/`）

| 技能 | 至少包含 |
|---|---|
| upper-computer-architecture | 分层依赖（gui→viewmodel→application→domain→protocol→transport）、深模块/seam 词汇、ViewModel 不可变状态、线程边界、禁止反向依赖 |
| upper-computer-ux | 页面信息层级/主次操作/实时数据/曲线/日志/参数/报警/标定/连接状态；Design Token（色彩/字号/间距）；高 DPI；危险操作确认；加载与错误态 |
| device-state-machine | 未发现/已发现/连接中/已连接/执行中/成功/失败/断开/自动重连/重连失败/用户取消/超时 的状态矩阵与 UI 反馈 |
| desktop-ui-review | 综合 Qt UI 设计、Design Engineering、桌面交互、工业安全、状态完整性、键盘/高 DPI、UI 线程与性能 |
| pyside6-development | MVC、Signal/Slot、QThread/QThreadPool、QSS 应用级主题、布局管理、高 DPI、pytest-qt 测试边界（PySide6 命名，非 PyQt6） |
| protocol-contract | V1 帧/命令/60B 状态/28B 目标/result/fault 的审查清单与 fixture 对照 |

## 9. 精确安装计划（第二阶段，仅在用户确认后执行）

### 9.1 前置

```bash
# 备份 Codex 配置
cp ~/.codex/config.toml ~/.codex/config.toml.bak.$(date +%Y%m%d%H%M%S)
# 上位机工作区快照（当前 git 工作区很脏，先 git status 确认边界）
cd /Users/wangzilin/PycharmProjects/ZEROARM_UpperComputer && git status --short
```

### 9.2 安装纯文本/外部 Skills（已实测可用的安装器命令）

```bash
INSTALLER=~/.codex/skills/.system/skill-installer/scripts/install-skill-from-github.py
python3 "$INSTALLER" --repo TheQtCompanyRnD/agent-skills --path skills/qt-ui-design
python3 "$INSTALLER" --repo emilkowalski/skills --path skills/emil-design-eng
python3 "$INSTALLER" --repo obra/superpowers --path skills/systematic-debugging
python3 "$INSTALLER" --repo mattpocock/skills --path skills/engineering/codebase-design   # 可选
python3 "$INSTALLER" --repo mattpocock/skills --path skills/engineering/tdd               # 可选
```

安装器默认写入 `~/.codex/skills/<name>`。官方手册 USER 路径为 `~/.agents/skills`：安装后若新会话未发现，移动到 `~/.agents/skills/` 或重启 Codex。

### 9.3 自建项目级 Skills（skill-creator）

```bash
CREATOR=~/.codex/skills/.system/skill-creator/scripts
mkdir -p /Users/wangzilin/PycharmProjects/ZEROARM_UpperComputer/.agents/skills
python3 "$CREATOR/init_skill.py" upper-computer-ux --path /Users/wangzilin/PycharmProjects/ZEROARM_UpperComputer/.agents/skills
# 同理：upper-computer-architecture / device-state-machine / desktop-ui-review / pyside6-development / protocol-contract
# 完成后逐个校验：
python3 "$CREATOR/quick_validate.py" /Users/wangzilin/PycharmProjects/ZEROARM_UpperComputer/.agents/skills/upper-computer-ux
```

### 9.4 安装 MCP

```text
Codex App → Settings → MCP servers → Add Server → Streamable HTTP
URL: https://qt-docs-mcp.qt.io/mcp
```

CLI 等价：`codex mcp add qt-docs --url https://qt-docs-mcp.qt.io/mcp`（需按本机 CLI 实际参数校验后再执行）。

### 9.5 验证

```text
1. 新会话执行 /skills，确认 qt-ui-design、emil-design-eng、systematic-debugging、自建技能可见。
2. qt-ui-design：审查 UpperComputer/src/zeroarm_desktop/gui/pages/connection.py，要求输出信息层级/操作流程/状态设计/高 DPI/键盘无障碍。
3. systematic-debugging：对 Mock 注入 CRC 错误/丢帧，确认根因调查流程生效。
4. qt-documentation-mcp：调用 qt_documentation_search 查 "PySide6 QThread" 与 "QWidget"，记录是否命中。
5. 自建技能：跑一次桌面 UI 审查 + 设备状态机审查，核对输出符合 SKILL.md 要求。
6. 检查配置变更：git diff ~/.codex/config.toml（如有）；确认无多余全局改动。
```

### 9.6 回滚

| 项 | 位置 | 卸载方法 |
|---|---|---|
| 外部 Skills | `~/.codex/skills/<name>` | `rm -rf` 对应目录（本调查已实测删除 4 个技能可完全恢复） |
| 自建 Skills | 仓库根 `.agents/skills/<name>` | 删除目录（未提交前 git 可丢弃；提交后正常提交删除） |
| qt-documentation-mcp | `~/.codex/config.toml` `[mcp_servers.*]` | 从 App MCP 设置移除，或恢复 9.1 的备份文件 |
| Context7（若装） | `~/.codex/config.toml` + `AGENTS.md` | 移除配置段 + 删除 AGENTS.md 中的指令行 + 撤销 API key |
| 插件（Superpowers 等） | Codex App Plugins | Plugins → Installed → Uninstall；新会话生效 |
| mcp-windows | MCP 配置 + 下载目录 | 移除 MCP 配置 + 删除 Release 二进制 |

## 10. 执行限制声明

本报告仅完成第一阶段调查。**在用户明确确认前：不安装任何 Skill/Plugin/MCP、不修改 Codex 配置、不运行未知脚本、不全局安装 npm 包、不修改项目依赖、不删除现有工具、不创建 Figma 文件、不授予桌面控制权限。**

## 11. 第二阶段执行记录（2026-08-01，用户确认后逐步执行）

### 11.1 前置备份

- `~/.codex/config.toml` → `~/.codex/config.toml.bak.20260801213846`（恢复命令：`cp ~/.codex/config.toml.bak.20260801213846 ~/.codex/config.toml`）。
- 上位机 git 工作区确认（R15 半成品仍为未提交状态，本次未改动任何项目源码/测试）。

### 11.2 已安装外部 Skills（用户级 `~/.codex/skills/`）

| 技能 | 来源 | 安装路径 |
|---|---|---|
| qt-ui-design | TheQtCompanyRnD/agent-skills main@71d6c10d | `~/.codex/skills/qt-ui-design` |
| emil-design-eng | emilkowalski/skills main@70744e38 | `~/.codex/skills/emil-design-eng` |
| systematic-debugging | obra/superpowers v6.2.0 | `~/.codex/skills/systematic-debugging` |
| codebase-design | mattpocock/skills v1.1.0 | `~/.codex/skills/codebase-design` |

卸载命令示例：`rm -rf ~/.codex/skills/<name>`（本调查已实测可完全恢复）。

### 11.3 已创建项目级自建 Skills（仓库根 `.agents/skills/`，未提交）

全部通过 skill-creator `quick_validate.py` 校验（`Skill is valid!`）：

```text
.agents/skills/upper-computer-architecture/
.agents/skills/upper-computer-ux/
.agents/skills/device-state-machine/
.agents/skills/desktop-ui-review/
.agents/skills/pyside6-development/
.agents/skills/protocol-contract/
```

每个包含 `SKILL.md` + `agents/openai.yaml`（UI 元数据）。内容以本项目分层、V1 契约、
`AGENTS.md`、`docs/03` 等实测事实为基准编写。

### 11.4 已接入 MCP

- `qt-docs`（Qt 官方文档 MCP）：`streamable_http` → `https://qt-docs-mcp.qt.io/mcp`，状态 enabled。
- 移除命令：`codex mcp remove qt-docs`。
- 说明：MCP 与新安装的技能需**新会话/重启 Codex** 后生效；当前会话不会自动加载。

### 11.5 待办（下一步可选）

1. 重启/新会话后执行 `/skills`，确认 4 个外部 + 6 个自建技能可见；用 `qt_documentation_search` 实测 PySide6 覆盖。
2. 可选补装：mattpocock `tdd`（`--repo mattpocock/skills --path skills/engineering/tdd`）。
3. 条件项：Context7（Qt MCP 不覆盖 PySide6 时）、mcp-windows（Windows 验收阶段）。
4. 修复 R15 未提交改动的质量门（prefer_mock 默认回归 + ruff 9 处），与本次安装无关、尚未处理。
5. `.agents/` 为 untracked，是否需要独立提交由用户决定。

## 附录 A：调查证据来源

- OpenAI Codex 官方手册（2026-08-01 抓取）：技能发现路径、插件目录、MCP 接入。
- TheQtCompanyRnD/agent-skills main@71d6c10d：全部 SKILL.md 原文、LICENSE（BSD-3-Clause OR Qt Commercial）、docs/mcp/setup-manual.md 与 index.md。
- mattpocock/skills v1.1.0（MIT）：improve-codebase-architecture / domain-modeling / codebase-design / code-review / tdd SKILL.md 原文。
- obra/superpowers v6.2.0（MIT）：systematic-debugging SKILL.md、README Codex 安装段。
- backnotprop/plannotator v0.9.3（MIT OR Apache-2.0）：README、apps/codex/README.md（Codex Stop hook 支持范围）。
- sbroenne/mcp-windows v1.3.9（MIT）：README（UIA 语义定位、DPI、LLM 测试、standalone MCP 配置）。
- nextlevelbuilder/ui-ux-pro-max-skill v2.9.0（MIT）：README、README.zh.md、SKILL.md、cli/package.json（uipro 支持 `--ai codex`）、克隆审计未发现遥测。
- emilkowalski/skills main@70744e38（MIT）：7 个 SKILL.md 原文。
- anthropics/skills main@b29e7cf6（Apache-2.0）：frontend-design SKILL.md。
- microsoft/skills main@4a2873fa（MIT）：frontend-design-review SKILL.md（.github/skills/）。
- oimiragieo/agent-studio（v3.x 活跃）：pyqt6-ui-development-rules SKILL.md 全文；根目录 LICENSE 文件不存在（未确认）。
- 官方 Codex 插件目录/社区报道：Figma、Playwright、Superpowers 插件存在性。
- Context7 官方 Codex 文档页：`ctx7 setup --codex`、插件安装、config 写入行为。
- GitHub 官方 MCP：github/github-mcp-server 仓库。
- 本机实测：`codex-cli 0.146.0-alpha.9.2`、插件清单、config.toml、技能目录、`git ls-remote` 各仓库 HEAD/tag、安装器实测安装与删除。

## 附录 B：无法确认项

| 项 | 状态 | 已检查来源 |
|---|---|---|
| qt-documentation-mcp 是否覆盖 PySide6/Qt for Python 文档 | **无法确认**（官方只声明 Qt 6.8.4/6.11.0 C++ 模块文档） | Qt MCP index.md、PulseMCP、doc.qt.io |
| oimiragieo/agent-studio 许可证 | **无法确认**（根目录无 LICENSE 文件） | raw 探测 LICENSE/LICENSE.md/LICENSE.txt/COPYING/LICENSES.md 均 404 |
| Servo MCP 的 Codex 兼容性与维护状态 | **无法确认**（仅 npm 元数据） | npm registry |
| Supercent/Mistakenot code-review 许可证 | **无法确认** | 聚合站点快照 |
| Codex App 是否同时发现 `~/.codex/skills` 与 `~/.agents/skills` 用户级技能 | 需安装后实测 | 官方手册（USER=~/.agents/skills）与本机 SYSTEM=~/.codex/skills/.system |
