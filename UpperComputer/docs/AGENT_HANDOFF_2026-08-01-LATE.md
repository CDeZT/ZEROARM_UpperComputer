# 上位机 Agent 交接（2026-08-01 晚 · 中断交接）

面向**下一个编码 Agent**。本轮用户要求**停下所有任务并交接**，R15 **未完成**，工作区有未提交改动。

## 1. 仓库与分支

| 项 | 值 |
|---|---|
| 上位机仓 | `ZEROARM_UpperComputer`，主目录 `UpperComputer/` |
| 分支 | `master` |
| 已提交 tip | `cff0480` `feat(gui): wire session recording, evidence, and product page flows` |
| 远程 | 以 `git status` / `git log` 现场为准；**本轮未 commit、未 push** |

交接前请现场执行：

```bash
cd /Users/wangzilin/PycharmProjects/ZEROARM_UpperComputer
git status --short
git log --oneline -10
cd UpperComputer && uv sync --locked
uv run ruff format --check .
uv run ruff check .
uv run mypy
uv run pytest -q
# 若需跳过历史资产问题（本轮已修 manifest，一般不必 ignore）：
# uv run pytest -q --ignore=tests/model3d/test_assets.py
```

## 2. 进度事实

```text
已完成并提交：R1～R14（Mock GUI 主路径可演示）
本轮目标：R15 打包/发布刷新 + 部分 UI/启动体验优化
本轮结果：部分落地，未跑通完整质量门，未独立提交
协议 V2：pending，禁止在用户说「确认实施协议 V2」前改 MCU
Serial：默认只读；Mock 可动作；真机动作需单独授权
```

### R 计划表

| 单元 | 内容 | 状态 |
|---|---|---|
| R1～R14 | V1 迁移 + Mock 成品化 | **已提交完成** |
| **R15** | **打包发布刷新** | **进行中 / 中断** |

## 3. 本轮已改但未提交（重要）

### 3.1 新文件（untracked）

- `UpperComputer/docs/AGENT_HANDOFF_2026-08-01.md`（早前交接）
- `UpperComputer/docs/USER_GUIDE.md`（本轮新增用户指南）
- `UpperComputer/docs/KNOWN_LIMITATIONS.md`（本轮新增已知限制）
- `UpperComputer/docs/CAPABILITY_MATRIX.md`（本轮新增能力矩阵）
- `UpperComputer/src/zeroarm_desktop/cli.py`（启动参数解析）

### 3.2 已修改（modified）

- `UpperComputer/src/zeroarm_desktop/bootstrap.py`：接入 CLI、`--version`、logging、launch options
- `UpperComputer/src/zeroarm_desktop/gui/shell.py`：导航分组、header 提示、safe-mode 占位 3D、主题状态、`launch_options`
- `UpperComputer/src/zeroarm_desktop/gui/theme.py`：深浅主题样式增强
- `UpperComputer/src/zeroarm_desktop/gui/pages/connection.py`：`prefer_mock`、副标题/安全提示
- `UpperComputer/packaging/build_portable.py`：`--dry-run` 清单、发布文档打包、`SHA256SUMS`、manifest schema v2、非 Windows 提示
- `UpperComputer/resources/robot_model/manifest.json`：**已按磁盘实际文件重算** GPL-2.0 与 URDF 的 sha256/size（修复预存 `test_assets` 失败）
- `UpperComputer/tests/packaging/test_packaging_artifacts.py`：CLI / dry-run / 文档存在性
- 若干交接/状态文档：`IMPLEMENTATION_STATUS.md`、`AGENTS.md`、`README.md`、`10/11/12` 文档、`START_HERE.md` 等（多为 R14 后文档同步，夹带在工作区）

### 3.3 勿提交

- `.idea/`、`.DS_Store`、根目录 `MCU 源码路径.md`、各类 `__pycache__`

## 4. 已知未完成 / 风险

1. **R15 未完成**：Windows 真机 PyInstaller 产物、干净无 Python 环境烟雾、Inno 安装/升级/卸载实测**未做**（当前是 macOS 开发机）。
2. **完整 pytest / ruff / mypy 本轮中断前未作为最终门禁重跑**；下一 Agent 必须重跑，不能假设绿。
3. **`ConnectionPage(prefer_mock=...)`** 已接线；若测试仍用旧构造应兼容（`prefer_mock` 默认 True）。
4. **`tests/packaging` dry-run** 通过 `importlib` 加载 `packaging/build_portable.py`，避免与标准库 `packaging` 包名冲突。
5. **UI 优化仅壳层**（导航分组/主题/连接页文案）；各功能页未做深度视觉统一。
6. 用户明确：**先做 Windows 发布主线**；macOS `.app` 非本轮重点。

## 5. 产品/硬件契约（不可忘）

- 协议：**仅 V1**（115200，单请求在途，GET_STATE 60B）
- Profile：`zeroarm_g474_v1_partial`，可用轴 mask **`0x1D`**（J1/J3/J4/J5）
- J2/J6 Unavailable；非零目标必须拒绝
- HOME 顺序：J5 → J4 → J3 → J1
- 域内关节单位：int urad
- Serial 禁止默认动作；夹爪动作未标定拒绝

## 6. 建议下一 Agent 任务顺序

1. **先验证本轮脏改动**：`ruff` / `mypy` / `pytest`；修编译/签名断裂。
2. **决定提交策略**（用户规则可原子提交）：
   - 建议拆分：`fix(assets): resync robot_model manifest hashes`  
     → `feat(app): add launch CLI and shell UX polish`  
     → `feat(packaging): dry-run inventory and release docs`  
     → `docs: R15 handoff + user guide / capability matrix`
3. **完成 R15 剩余**：
   - Windows 上 `uv run python packaging/build_portable.py --build`
   - 记录 dist ZIP/exe SHA256 到 `docs/20_RELEASE_ACCEPTANCE.md`
   - 勾选干净环境启动；Inno 若本机有则编译 setup
4. **不要**实施协议 V2；**不要**默认发 Serial 动作。

## 7. 本机路径

| 用途 | 路径 |
|---|---|
| 上位机仓库 | `/Users/wangzilin/PycharmProjects/ZEROARM_UpperComputer` |
| MCU 源码（macOS） | `/Users/wangzilin/STM32Cube/zero_arm_mcu` |
| 本地备忘（勿提交） | 根目录 `MCU 源码路径.md` |

## 8. 一句话启动（复制给新 Agent）

```text
读取 UpperComputer/docs/AGENT_HANDOFF_2026-08-01-LATE.md 与 IMPLEMENTATION_STATUS.md；工作区有未提交的 R15 半成品（CLI/UI/打包 dry-run/文档/资产哈希），先 git status + 全量质量门验证并修好，再按用户规则做原子提交；继续完成 R15 Windows 打包验收，遵守 AGENTS.md 与 SafetyGate，V1 only，Serial 默认只读，未授权不发动作；完成后更新状态文档并停止报告。
```

## 9. 必读清单

1. 本文  
2. `IMPLEMENTATION_STATUS.md`（仍写 R14 完成 / R15 下一；需下一 Agent 刷新）  
3. `AGENTS.md`  
4. `docs/USER_GUIDE.md` / `KNOWN_LIMITATIONS.md` / `CAPABILITY_MATRIX.md`  
5. `docs/08_PACKAGING_RELEASE_OPERATIONS.md` + `docs/20_RELEASE_ACCEPTANCE.md`  
6. 改接口时：`17_API_DATA_AND_FIXTURE_CONTRACTS.md`
