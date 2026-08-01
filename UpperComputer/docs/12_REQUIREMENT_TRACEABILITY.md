# 需求追踪基线 V2

更新时间：2026-08-01

## 1. 功能到当前路线

| 需求组 | 当前单元 | 核心证据 |
|---|---|---|
| 连接/身份 | R1、R3～R5 | V1 fixture、Mock/Serial contract、HELLO/GET_STATE只读报告 |
| 状态/监控 | R1、R5 | 60B解码、fault/result、Unknown、Unavailable、GUI测试 |
| HardwareProfile | R2、R5 | `0x1D`、J2/J6拒绝、readiness和页面可用性 |
| Homing | R3、R6 | Mock顺序+授权现场J5→J4→J3→J1、前后snapshot |
| 手动控制 | R2、R7 | SafetyGate、分轴动作、组合互锁、J2/J6永不发送 |
| 会话/自动回零 | R3、R8 | 保活、20秒静默、断开警告、重连不恢复动作 |
| 运动学/3D | R2、R5、R9 | 当前范围映射、FK/IK、ghost、路径约束 |
| 轨迹/回放 | R9、R10 | 逐点约束、≤50Hz、无burst、误差中止、现场证据 |
| 示教 | R3、R11 | 状态互斥、支撑、mask、raw/final状态；硬件门可延期 |
| 夹爪 | R1、R2、R12 | STS帧、只读诊断、校准profile、动作门；硬件门可延期 |
| 诊断/台架 | R1、R13 | 无透传、参数验证、命令审计、保护配置证据 |
| 固件运维 | R4、R13 | artifact/hash/target/SN/verify/reset/HELLO |
| 数据/性能 | R14 | schema、OperationEvidence、soak、队列和时延指标 |
| 打包/发布 | R15 | 无Python Windows、Mock、资源、升级保留、能力矩阵 |

## 2. 非功能需求证据

| 事实 | 设计 | 验证 |
|---|---|---|
| GUI不阻塞 | worker/queued signal/latest value | pytest-qt+性能注入 |
| 队列有界 | Transport/Recorder/plot fixed capacity | high-water和drop counter |
| V1单在途 | DeviceSession tracker | 并发轮询/动作排序测试 |
| Unknown不伪造 | optional/raw wrapper | Codec/ViewModel/GUI测试 |
| 危险超时不重发 | UnknownOutcome | Session E2E |
| 重连不恢复动作 | disarm on disconnect | Mock/Serial E2E |
| 中间路径安全 | sampled InterlockPolicy | 性质测试+危险中间点fixture |
| 数据可追溯 | OperationEvidence | SQLite roundtrip/export |
| 无Python发布 | PyInstaller portable | 干净Windows烟雾 |

## 3. 安全事实证据

| 安全事实 | 实现位置目标 | 证据 |
|---|---|---|
| 软件STOP非E-stop | 固定文案和帮助 | GUI文本审查 |
| J2/J6不可用 | HardwareProfile+最终payload检查 | Domain+Command E2E |
| HOME固定mask/顺序 | Homing service/view | Mock+授权现场证据 |
| J3/J4/J5互锁 | InterlockPolicy+path validator | 边界/性质/现场阈值测试 |
| 自动回零可见 | Session keepalive+silence warning | 虚拟时间+现场静默测试 |
| TEACH互斥 | Readiness+CommandService | 全动作族拒绝测试 |
| 夹爪未标定禁动作 | GripperProfile+SafetyGate | read-only/action分级测试 |
| 任意透传禁止 | restricted console/bench forms | GUI/应用边界测试 |

## 4. 维护规则

每个 R 单元完成时，把目标模块名替换为实际路径和测试名称，并链接完成记录。required
条目最终必须有 automated、manual、deferred-with-reason 三者之一；不能仅写“端到端已测”。
