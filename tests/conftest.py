r"""pytest 公共装置 —— fixture 都放这里，pytest 会自动读取

这个文件名是 pytest 的约定：
    放在 tests\ 目录下，pytest 会自动加载，不需要任何 import。
    tests\ 下所有测试文件都能直接使用这里定义的 fixture。
"""

import pytest

from framework.canoe_controller import CanoeController
from framework.config_loader import load_config, resolve_path
from framework.logger import get_logger

# 模块顶层只做【无副作用】的事：配日志、读 YAML
# ⚠️ 绝对不要在这里 CanoeController() —— 收集阶段就会执行，会连 CANoe
logger = get_logger()#调用logger文件的函数
CFG = load_config()#去config_loader调用函数


@pytest.fixture(scope="session")
def canoe():
    """测试用的 CANoe 控制器 —— 整个测试会话只创建一次

    scope="session" 的意义:
        19 个用例，如果每个都连一次 CANoe（冷启动约 7 秒），
        光连接就要 2 分钟；用 session 后只在最开始连接一次。

    yield 的用法:
        yield 之前 = 前置准备（所有用例开始前执行一次）
        yield 之后 = 后置清理（所有用例结束后执行一次）
        yield 出去的东西 = 测试函数收到的那个参数
    """
    logger.info("=" * 60)
    logger.info("测试会话开始：连接 CANoe")
    logger.info("=" * 60)

    c = CanoeController()#连接控制器，这是控制器的标准使用的地方和方法

    # 确保打开的是配置里指定的那个工程
    config_path = resolve_path(CFG["canoe"]["config_path"])#该函数在config_loder
    if c.config_name() == "":#在canoe_controller
        logger.info(f"当前没有打开的工程，打开 {config_path}")
        c.open_config(config_path)#在canoe_controller

    # 确保测量在跑（幂等：已经在跑就跳过）
    if not c.is_running():#在canoe_controller
        c.start_measurement()#在canoe_controller
        c.wait_for_sysvar("Engine", "EngineSpeedDspMeter", 0.0)#在canoe_controller

    yield c                                  # ← 把控制器交给测试用例

    logger.info("=" * 60)
    logger.info("测试会话结束（CANoe 保持打开，方便观察）")
    logger.info("=" * 60)

@pytest.fixture(scope="session")
def cfg():
    """把配置交给需要它的测试"""
    return CFG


def _reset(c):
    """把被测系统恢复到初始状态（这是辅助函数，不是 fixture）

    ⚠️ 不只是写完系统变量就完事 ——
       EngineSpeedDspMeter 是【输出】变量，要等一个完整的报文周期
       （100ms）才会跟着输入变化。所以必须等到它真的归零。
    """
    c.set_sysvar("Engine", "EngineStateSwitch", 0)#set_sysvar读取系统变量
    c.set_sysvar("Engine", "EngineSpeedEntry", 0.0)      # 注意 0.0，float
    c.set_sysvar("Lights", "HazardLightsSwitch", 0)
    c.set_sysvar("Test", "FaultInject", 0)

    # ★ 等显示真的更新（不是"写完就算"）
    c.wait_for_sysvar("Engine", "EngineSpeedDspMeter", 0.0)


@pytest.fixture(autouse=True)
def reset_system(canoe):
    """每个用例前后自动复位被测系统

    autouse=True:
        不用写成测试函数的参数，也会自动执行。

    为什么复位:
        上一个用例可能留下 2500 rpm、点火开着……
        不复位的话，测试结果会被上一个用例污染（"测试间耦合"）。

    为什么前后都要复位:
        前面复位 → 保证用例从干净状态开始
        后面复位 → 用例中途失败时，不会把脏状态留给下一个用例
    """
    _reset(canoe)
    yield
    _reset(canoe)