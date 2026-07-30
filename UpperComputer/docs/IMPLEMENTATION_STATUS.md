# 上位机实施状态

## 当前状态

```text
阶段：Mock轨迹回放完成
已完成实施单元：单元0～16
当前应用版本：0.1.0
上位机源码：工程基线及纯V1帧协议已创建
下一审查单元：单元17 Mock拖动示教
编码执行者：Kilo
```

## 已完成事实

- 产品需求、GUI、架构、协议提案、实施、测试、安全和打包规划已建立。
- 嵌套 `UpperComputer/AGENTS.md` 已建立。
- 精确实现蓝图、机器可读执行manifest以及API/fixture合同已建立。
- 参考项目已确认存在于仓库内。
- 当前V1协议和60字节GET_STATE布局已审计。
- 协议V2实现尚未批准。
- 机械臂尚未组装，真实动作测试未授权。
- MCU问题已重新分成A类确认语义问题、B类未接入能力、C类协议债和D类硬件事实。
- MCU修复计划已拆成MCU-R0～R12。
- MCU-RB0协议组帧边界已完成并提交`653b994`。
- MCU-RB1轨迹到达后停止重复发布已完成并提交`ebb271c`。
- 用户要求剩余确认的软件问题全部逐项修复，每项一个独立提交。
- 已建立Python 3.12、PySide6、src layout、uv锁定依赖和GUI入口。
- 最小离线窗口不连接串口、不加载模型且不发送硬件命令。
- ruff格式/lint、mypy严格类型检查和2项pytest-qt测试已通过。
- 独立虚拟环境锁定安装和离屏GUI事件循环启动/退出已通过。
- 已实现Dallas/Maxim CRC8、V1完整帧编码/校验和有界增量stream parser。
- MCU当前协议源码已逐项核对，HELLO请求/响应和result响应黄金帧已固化并记录哈希。
- 23项pytest通过，覆盖Hypothesis随机分块、粘包拆包、噪声、CRC、ETX、非法LEN、
  重置恢复、最大payload和固定种子百万字节输入。
- 已实现HELLO、GET_STATE、result、joint mask和SET_JOINT_TARGET V1 Codec。
- 60字节状态按明确小端偏移解码，28字节目标按明确大端字段编码；未知线上值保留。
- 单元2完成时ruff、mypy和45项pytest通过。
- 已建立bytes-only Transport契约、订阅生命周期和不可变链路统计。
- MockDevice真实解析V1请求bytes并生成60字节状态，支持确定性运动和字节级故障注入。
- 单元3完成时ruff、mypy和52项pytest通过。
- 已实现可取消Serial worker、部分写处理、有界队列和跨平台端口发现。
- pyserial全部行为由fake backend验证；现场未打开端口、未发送协议帧。
- 单元4完成时ruff、mypy和57项pytest通过。
- 已实现V1只读Session状态机、HELLO/GET_STATE握手、单请求在途和20/50/100 Hz轮询。
- Mock E2E经真实双端V1 bytes链路进入READONLY_READY，错误握手不会伪报就绪。
- 单元5完成时ruff、mypy和65项pytest通过。
- 已实现Pydantic版本化配置、跨平台数据路径、SQLite WAL migration和批量Recorder。
- 支持CSV/JSON会话导出、批量写入及有界队列丢弃统计。
- 单元6完成时ruff、mypy和69项pytest通过。
- 已实现正式MainWindow、稳定页面路由、全局状态区、通知中心及深浅主题。
- 全局STOP固定禁用并标记“软件停止，非急停”，没有连接任何Transport。
- 单元7完成时ruff、mypy和72项pytest通过。
- 已实现Mock/Serial选择、端口刷新、轮询率和Mock seed配置。
- GUI Mock连接通过真实Session完成HELLO/GET_STATE，展示握手时间线与V1身份。
- 单元8完成时ruff、mypy和74项pytest通过。
- 已实现Snapshot ViewModel、Dashboard、六轴表格和pyqtgraph target/actual/error曲线。
- 100 Hz输入经latest-value与最高60 FPS渲染解耦，plot ring固定为6000样本。
- V1缺失velocity/current/online明确显示“V1未提供”，不伪造为0。
- 单元9完成时ruff、mypy和77项pytest通过。
- 已从工作区只读参考项目导入1个URDF、7个二进制STL和GPL-2.0许可证。
- 运行时manifest记录相对来源、文件大小和SHA-256，不包含用户目录绝对路径。
- URDF验证为单根树、7 links/6 joints；7 meshes共371,786三角形且bounds合理。
- 单元10完成时ruff、mypy和83项pytest通过。
- 已集中实现六轴MCU urad到URDF rad映射、限位检查和可逆转换。
- URDF FK输出7个link世界变换，复现URDF零位与modified-DH零位黄金姿态。
- 坐标报告明确模型证据完成但实机编码器零点/方向仍未验证。
- 单元11完成时ruff、mypy和88项pytest通过。
- 已实现NumPy二进制STL加载、actual/ghost双场景、世界轴、网格和有界末端tail。
- `page_workspace_3d`在原生Windows使用PyOpenGL渲染，offscreen自动降级为场景数据模式。
- 原生OpenGL探针加载14个mesh item并生成116,808字节非空截图。
- 单元12完成时ruff、mypy和93项pytest通过。
- 已实现纯SafetyGate、命令分级、全部拒绝原因、preview hash和5秒ArmContext。
- CommandService执行前重新核验token、hash、generation、校准、命令族和轴mask。
- SafetyGate核心143 statements/42 branches均达到100%覆盖；全量105项pytest通过。
- 已实现`page_manual_joint`相对/绝对预览、5秒Arm、Mock发送和最高50 Hz hold-to-run。
- release、窗口失焦、导航、全局软件STOP、断线和shutdown均撤销hold/Arm且不自动恢复。
- Mock动作通过SafetyGate、DeviceSession、V1 SET_JOINT_TARGET bytes和GET_STATE反馈闭环。
- 原生GUI烟雾完成generation 1→2并生成93,699字节3D截图；全量110项pytest通过。
- 已实现版本化不可变Trajectory、JSON往返、限位/时间/速度验证和内容SHA-256。
- 已实现线性重采样、移动平均、速度缩放、undo/redo和`page_trajectory`。
- 表格选点、六轴曲线和3D ghost已联动；单元15全量115项pytest通过。
- 已实现可注入monotonic时钟的PlaybackEngine、50 Hz上限和迟到点丢弃。
- pause/resume移动时间基准，abort停止调度，禁止burst补发积压点。
- 轨迹页Mock回放走DeviceSession与真实V1 bytes；单元16全量117项pytest通过。

## 待审批

- 未来协议V2具体实施方案。
- 未来高波特率方案。
- 机械臂组装完成后的动作测试范围。

## 下一轮边界

当前连续里程碑的下一单元为单元17：

- Mock TEACH_START/STOP状态机和有界raw recorder。
- PC monotonic/wall时间与V1缺失时间字段。
- review另存processed轨迹且保留parent raw hash。

仅允许Mock轨迹开发；真实Serial保持只读，不发送任何动作命令。

若当前任务继续MCU修复，按`13_MCU_REMEDIATION_PLAN.md`选择一个尚未完成的
软件问题，先以失败测试固定语义，完成验证和独立提交后停止，不执行危险动作。
