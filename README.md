# CANoe + Python 自动化测试框架

> 两条测试主线：
> 1. **CANoe 总线测试**：通过 COM 接口控制 CANoe，读写系统变量，验证仪表响应
> 2. **UDS 诊断测试**：在虚拟 CAN 总线上用 `udsoncan` 发送诊断请求，验证会话、安全访问与负向路径
>
> 基于 pytest 组织用例，支持配置化管理、分级日志与 HTML 测试报告。

## 1. 项目简介

覆盖车载电子测试的两类典型场景：

| 场景 | 被测对象 | 技术栈 |
|---|---|---|
| 总线功能 / 性能测试 | CANoe Easy 工程（Simulated Bus） | pywin32 COM + pytest |
| 诊断协议测试 | 自写 ECU 模拟器（虚拟 CAN） | python-can + can-isotp + udsoncan |

具体覆盖：

- **总线**：转速、灯光、响应时间、接口契约、故障注入
- **诊断**：会话控制、读 / 写 DID、安全访问、负向 NRC、S3 时序
- **工程化**：YAML 配置、分级日志、HTML 报告、有状态用例隔离

> 无 VN 硬件，全部基于 CANoe **Simulated Bus** 与 python-can **virtual** 运行。

## 2. 快速开始

```bash
# 1. 创建虚拟环境
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# 2. 安装依赖
pip install -r requirements.txt

# 3. 运行 CANoe 总线测试
python -m pytest

# 4. 运行 UDS 诊断测试（纯虚拟总线，不需要 CANoe）
python -m pytest uds_tests
```

> ⚠️ **必须在项目根目录下运行**，因为配置、报告、日志路径都相对于项目根目录。

## 3. 项目结构

```
canoe-regression-framework/
├── README.md                    项目说明（本文件）
├── requirements.txt             依赖清单（含 Python 版本要求）
├── pytest.ini                   pytest 配置：标签 / 超时 / 自动生成报告
│
├── config/
│   └── test_config.yaml         唯一配置来源：工程路径 / 超时 / 阈值 / 日志级别
│
├── framework/                   框架代码（换一个 CANoe 工程也不用改）
│   ├── __init__.py
│   ├── logger.py                日志：控制台彩色输出 + 文件落盘
│   ├── config_loader.py         读取 YAML，并以 __file__ 锚定项目根目录
│   └── canoe_controller.py      CANoe 控制：COM 接口 / 测量启停 / 系统变量读写
│
├── tests/                       测试用例（与被测系统强相关）
│   ├── conftest.py              公共 fixture：CANoe 连接 + 每个用例前后自动复位
│   ├── test_smoke.py            冒烟测试（3 个）
│   ├── test_engine.py           功能测试（5 个）
│   ├── test_engine_param.py     参数化测试（8 个）
│   ├── test_response_time.py    响应时间性能测试（3 个）
│   └── test_contract.py         接口契约测试（3 个）
│
├── configs/
│   └── Easy/                    CANoe 工程副本（被测对象）
│       ├── Easy.cfg
│       ├── CANdb/easy.dbc
│       └── Nodes/*.can
│
├── uds/                         UDS 协议实现与 ECU 模拟器
│   ├── u1_session_machine.py    会话状态机：会话切换 / S3 超时 / NRC
│   ├── u2_isotp_multiframe.py   ISO-TP 分片演示：SF/FF/CF/FC
│   ├── u3_security_access.py    0x27 安全访问：种子 / 密钥 / 锁定
│   ├── u4_ecu_simulator.py      ECU 模拟器：跑在 CAN 总线上
│   ├── u5_udsoncan_demo.py      udsoncan 演示
│   └── u*_exercise.py           练习题与对账脚本
│
├── uds_tests/                   UDS 诊断自动化用例（不依赖 CANoe）
│   ├── conftest.py              ECU + udsoncan 夹具
│   ├── test_uds_basics.py       正向与基础负向
│   ├── test_uds_negative.py     NRC 负向覆盖
│   └── test_uds_state.py        状态机与时序
│
├── logs/                        运行时生成：每次运行一个日志文件
└── reports/                     运行时生成：report.html
```

## 4. 设计说明

### 4.1 为什么分 `framework/` 和 `tests/` ？

判断标准只有一个：**换一个 CANoe 工程，哪些文件要改？**

| 目录 | 内容 | 换工程要改多少 |
|---|---|---|
| `framework/` | `__init__.py` / `logger.py` / `config_loader.py` / `canoe_controller.py`（4 个文件） | **0 行** |
| `config/` | `test_config.yaml` | 改 `canoe.config_path` 一行 |
| `tests/` | `conftest.py` + 5 个 `test_*.py` | **全部要重写** |

三条理由：

1. **职责不同**：`framework/` 负责"怎么测"（连接、日志、配置、等待），`tests/` 负责"测什么"（转速、灯光）
2. **依赖不同**：`framework/` 只依赖 pywin32 / colorlog / PyYAML；`tests/` 还依赖 pytest，以及 **Easy 工程专有的系统变量名**
3. **生命周期不同**：`framework/` 换工程能直接复用；`tests/` 是 Easy 工程专属，换工程必须重写

> 注：本项目**没有 `src/` 目录**。早期原型版本曾把代码放在 `src/`（见旧项目 `CANoeAutoTest`），
> 重构后统一收进 `framework/`，避免"业务代码 / 框架代码 / 测试代码"混在一起。

### 4.2 为什么用 YAML 配置，而不是写在代码里？

目前有 4 组配置：

| 组 | 内容 |
|---|---|
| `canoe` | 工程路径、CANoe 是否可见 |
| `timeouts` | 测量超时、系统变量等待超时、轮询间隔 |
| `thresholds` | 响应时间判定阈值 |
| `logging` | 日志级别、日志目录 |

**如果把这些值写死在代码里，改一个参数要动不同的文件：**

| 要改什么 | 写死在代码里 → 改哪 | 现在 → 改哪 |
|---|---|---|
| 工程路径 | `tests/conftest.py` | `config/test_config.yaml` |
| 测量超时 | `framework/canoe_controller.py` | 同上 |
| 响应时间阈值 | `tests/test_response_time.py` | 同上 |
| 日志级别 | `framework/logger.py`（默认参数） | 同上 |

**4 个文件 → 1 个文件。**

#### 两个实测证据（证明配置真的接上了，不是摆设）

1. `thresholds.max_response_ms: 200 → 1`
   → 3 个性能用例立刻失败，报错 `响应 104ms 超过上限 1ms`
2. `logging.level: INFO → DEBUG`
   → 控制台立刻出现原本被过滤掉的 DEBUG 日志

> **单向验证不够。**
> 如果只看到"改了配置程序没崩"，说明不了任何问题 —— 因为"配置生效"和"配置失效"可能产生相同的结果。
> **必须让两种假设产生不同的结果**，才算证明配置真的生效。

### 4.3 为什么用 session 级 fixture 管理 CANoe 连接？

**实测数字：**

- CANoe 冷启动约 **7.4 秒**
- 22 个用例，若每个用例都连一次：7.4 × 22 ≈ **2.7 分钟**
- 用 `scope="session"`：整个测试会话只连 **1 次**

两条理由：

1. **初始化开销不可接受** —— 2.7 分钟里 2.6 分钟都在等连接
2. **CANoe 是单例资源** —— 同一台机器只能有一个 CANoe 实例，反复连/断容易留下脏状态

**实测整套耗时（22 个用例）：**

| 场景 | 耗时 |
|---|---|
| CANoe 已在运行（热） | 约 **2.7 秒** |
| CANoe 刚启动（冷） | 约 **14.6 秒** |

> 冷热差异约 5 倍 —— 这也是为什么看测试耗时前，要先确认 CANoe 的状态。

### 4.4 为什么要"轮询等待"，而不是 `sleep` 固定时间？

> sleep 是在赌"最坏情况有多久"，轮询是在等"条件真的发生了"。
> 前者用固定的时间猜一个不确定的完成时刻，后者把判断依据交给系统真实状态。

**本项目真实踩过的坑：**

- `restart_measurement` 早期写的是 `time.sleep(1)` 后直接 `Start()` —— 既硬编码，又在赌
- `conftest.py` 的 `_reset()` 只写系统变量、不等显示更新
  → `test_initial_state` **偶发失败（5 次挂 2 次）**
  → 实测：复位后立即读 `EngineSpeedDspMeter` 仍是 **3.5**（旧值），真正归零需要 **89~135 ms**
  → 加上 `wait_for_sysvar` 等待后，连跑 **10 次全绿**

**根因**：`EngineSpeedDspMeter` 是**输出**变量，要经过一个完整的 **100ms 报文周期**才会跟着输入变化。

> 同一个原则在本项目里出现了多次：
> `Measurement.Start()` 返回 ≠ 测量已启动；
> `Measurement.Stop()` 返回 ≠ 测量已停止；
> `set_sysvar(输入)` 返回 ≠ 输出已更新。

## 5. UDS 诊断自动化

### 5.1 为什么 `uds_tests/` 不放进 `tests/`

| | `tests/` | `uds_tests/` |
|---|---|---|
| 被测对象 | CANoe + Easy 工程 | 自写 ECU 模拟器 |
| 依赖 | CANoe 许可证、COM | `python-can` 虚拟总线 |
| 启动成本 | 冷启动约 7.4 秒 | 毫秒级 |
| 是否需要硬件 | 否（Simulated Bus） | 否 |

如果把 UDS 用例放进 `tests/`，每个用例都会被 `tests/conftest.py` 的
session fixture 拉起 CANoe —— 而 UDS 根本不需要它。

因此 `pytest.ini` 的 `testpaths` 只包含 `tests`，UDS 用例需显式指定目录运行。

### 5.2 架构

```text
uds_tests/                 pytest 用例
    ↓
udsoncan.Client            诊断服务（0x10 / 0x22 / 0x27 / 0x2E / 0x3E）
    ↓
can-isotp                  分片与重组（SF / FF / CF / FC）
    ↓
python-can virtual         虚拟 CAN 总线
    ↓
uds/u4_ecu_simulator.py    自写 ECU 模拟器
    ↓
uds/u3_security_access.py  会话状态机 + 安全访问
```

### 5.3 覆盖范围

| 状态 | 服务 | 用例 |
|---|---|---|
| ✅ | `0x10` 会话控制 | 会话切换、非法会话 `0x12` |
| ✅ | `0x22` 读 DID | 正常读取、未知 DID `0x31` |
| ✅ | `0x27` 安全访问 | 种子、错误密钥 `0x35`、顺序错误 `0x24`、锁定 `0x36`、冷却 `0x37` |
| ✅ | `0x2E` 写 DID | 未解锁 `0x33`、解锁后写入成功 |
| ✅ | `0x3E` 心跳 | 正响应 |
| ✅ | 状态 | S3 超时、会话切换自动上锁 |
| ⬜ | `0x19` / `0x14` | DTC 读取与清除（后续） |
| ⬜ | `0x31` / `0x2F` | 例程控制 / IO 控制（后续） |
| ⬜ | `0x34`~`0x37` | 刷写流程（后续） |

### 5.4 运行

```powershell
# 全部 UDS 用例
python -m pytest uds_tests -v

# 只跑负向
python -m pytest uds_tests/test_uds_negative.py -v

# 生成独立报告
python -m pytest uds_tests --html=reports/uds_report.html --self-contained-html
```

### 5.5 两个设计要点

**① 有状态对象必须做用例隔离**

ECU 会记住会话、解锁状态、失败次数和锁定时间。
`uds_tests/conftest.py` 用 `autouse=True` 的 `reset_state` 在每个用例前全部清零，
否则会出现"单条能过、整套失败"。

**② 时间参数必须可注入**

S3 标准和冷却时间在真实 ECU 上是秒级。测试里把
`s3_timeout` / `lock_seconds` 调短后注入，避免测试套件被"真实等待"拖慢。

### 5.6 CANoe 诊断仿真（工具链验证）

项目内置了一条 CANoe 侧的诊断链路，用于验证"工具链视角"下的 UDS：

| 组件 | 配置 |
|---|---|
| 诊断描述 | CANoe 自带 `GenericUDS.cdd` |
| ECU 标识 | `SimEcu` |
| 传输层 | 请求 `0x7E0` / 响应 `0x7E8` |
| ECU 仿真节点 | `configs/Easy/Nodes/UdsSimEcu.can` |

使用步骤：

1. 打开 `configs/Easy/Easy.cfg`
2. `Diagnostics → Diagnostic/ISO TP` → 确认 `SimEcu` 挂在 `easy` 网络
3. F9 启动测量
4. `Diagnostics → Diagnostic Console` → 发送 `$10` / `$22`

已实测：

| 请求 | 响应 |
|---|---|
| `10 03` | `50 03 00 32 01 F4` |
| `22 F1 86` | `62 F1 86 03` |
| `22 F1 96` | `7F 22 31` |

> 该 CAPL 节点用原始单帧实现 UDS，不依赖 CDD，
> 因此可以独立验证传输层与协议字节。

## 6. 如何扩展

### 6.1 加一个新测试用例

```python
def test_engine_speed_1500(canoe):
    """点火 + 油门 1500 rpm → 仪表显示 1.5"""
    canoe.set_sysvar("Engine", "EngineStateSwitch", 1)
    canoe.set_sysvar("Engine", "EngineSpeedEntry", 1500.0)

    ok, waited = canoe.wait_for_sysvar("Engine", "EngineSpeedDspMeter", 1.5)
    assert ok, f"等待超时（{waited:.2f}s）"
```

要点：

1. 函数名必须以 `test_` 开头
2. 参数 `canoe` 来自 `conftest.py` 的 session fixture —— **不需要 import**
3. **不要自己写复位** —— `conftest.py` 里 `autouse=True` 的 `reset_system` 会在每个用例前后自动复位
4. 写完直接 `python -m pytest`，pytest 自动收集，**不需要注册**

### 6.2 换一个 CANoe 工程

1. **改配置**：`config/test_config.yaml` → `canoe.config_path` 指向新工程
2. **`framework/` 不用改**
3. **`tests/` 要按新工程改**：
   - 系统变量的命名空间和变量名（本项目是 `Engine` / `Lights`，新工程不同）
   - 期望值（输入 → 输出的换算关系）
   - `conftest.py` 的 `_reset()` 里复位哪些变量
4. **先跑冒烟验证**：`python -m pytest -m smoke`

> **判断原则**：这个文件里有没有"Easy 工程"的东西？
> 有 → 要改；没有 → 不用动。

## 7. 常用命令

### 环境准备（每次打开新终端）

```powershell
cd D:\Test\canoe-regression-framework
.\.venv\Scripts\Activate.ps1
```

### 运行测试

| 命令 | 说明 |
|---|---|
| `python -m pytest` | 运行全部用例 |
| `python -m pytest -q` | 简洁输出 |
| `python -m pytest -m smoke` | 只跑冒烟测试（3 个） |
| `python -m pytest -m "not smoke"` | 跑除冒烟外的全部用例 |
| `python -m pytest tests/test_engine.py` | 只跑一个文件 |
| `python -m pytest tests/test_engine.py::test_engine_speed_1000` | 只跑一个用例 |
| `python -m pytest -k "2500"` | 按用例名模糊筛选 |
| `python -m pytest -x` | 第一个失败就停止 |
| `python -m pytest --lf` | 只跑上次失败的用例 |
| `python -m pytest uds_tests` | 跑 UDS 诊断用例（不启动 CANoe） |
| `python -m pytest uds_tests/test_uds_negative.py` | 只跑 UDS 负向用例 |

### 报告与日志

| 命令 | 说明 |
|---|---|
| `python -m pytest --html=reports/report.html --self-contained-html` | 生成独立 HTML 报告 |
| `start reports\report.html` | 打开报告 |
| `Get-Content logs\*.log -Tail 20` | 查看最近日志 |

### 静态检查

| 命令 | 说明 |
|---|---|
| `ruff check tests\ framework\` | 检查代码规范 |
| `ruff check tests\ framework\ --diff` | 只显示会改什么，不动文件 |
| `ruff check tests\ framework\ --fix` | 自动修复 |

### 调试

| 命令 | 说明 |
|---|---|
| `python -m pytest --collect-only -q` | 只收集用例，不运行 |
| `python -m pytest --log-cli-level=DEBUG` | 临时查看 DEBUG 级别日志 |
| `python -m pytest --markers` | 列出所有已注册标签 |
| `python -m pytest --fixtures` | 列出所有可用 fixture |
