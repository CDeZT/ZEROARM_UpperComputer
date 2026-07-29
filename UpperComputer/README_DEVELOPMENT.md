# ZeroArm Desktop 开发指南

## 环境

- Windows 为主要开发和发布平台，源码保持跨平台。
- Python 版本范围为 `>=3.12,<3.14`。
- 使用 `uv` 创建隔离环境并依据 `uv.lock` 复现依赖；不要提交 `.venv`。

## 初始化

在 `UpperComputer` 目录执行：

```powershell
uv python install 3.12
uv sync --locked
```

## 启动

```powershell
uv run python -m zeroarm_desktop
```

也可以使用安装的 GUI 入口：

```powershell
uv run zeroarm-desktop
```

当前工程基线不连接串口、不加载模型，也不发送任何硬件命令。

## 质量检查

```powershell
uv run ruff format --check .
uv run ruff check .
uv run mypy
uv run pytest -q
```

选择 mypy 作为类型检查器，因为它能与 Python 项目元数据一起集中配置，并可在
本地和 CI 中通过同一条命令复现。ruff 同时负责格式和 lint，pytest-qt 负责 Qt
窗口生命周期测试。

## 依赖策略

- 运行时和开发依赖声明在 `pyproject.toml`。
- `uv.lock` 必须随依赖变更一同提交。
- 更新依赖使用 `uv lock --upgrade-package <package>`，随后运行全部质量检查。
- 当前引入 PySide6、pyserial、pyqtgraph、Pydantic、SQLite标准库、测试、静态检查和
  Hypothesis性质测试工具；后续依赖按对应实施单元添加。
