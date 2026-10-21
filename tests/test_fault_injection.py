"""故障注入测试 —— 验证 DUT 对超范围输入的响应"""

import time

import pytest

from framework.logger import get_logger

logger = get_logger()


def sample_range(canoe, duration=1.0):
    """在一段时间内高频采样仪表值，返回 (最小值, 最大值)

    为什么要多次采样：
        注入帧每 20ms 发一次，但周期帧每 100ms 会把仪表打回 0。
        只读一次可能正好读到 0 —— 那是采样误差，不是功能正常。

    为什么不能只记最大值：
        EngineSpeed 在 DBC 里是【有符号 15 位】，
        超出范围的值会绕回负数 —— 只记最大值会把负数全丢掉。
    """
    values = []
    start = time.time()
    while time.time() - start < duration:
        values.append(canoe.get_sysvar("Engine", "EngineSpeedDspMeter"))
        time.sleep(0.01)
    return min(values), max(values)


@pytest.mark.regression
def test_fault_injection_reaches_display(canoe):
    """注入生效性：开启注入后，仪表应出现 12.0（12000 / 1000）

    这条不是测 DUT，是测【我们的注入工具本身】——
    注入都没生效，后面的断言全是假的。
    """
    canoe.set_sysvar("Test", "FaultInject", 1)
    try:
        lo, hi = sample_range(canoe, duration=1.0)
    finally:
        canoe.set_sysvar("Test", "FaultInject", 0)
        canoe.wait_for_sysvar("Engine", "EngineSpeedDspMeter", 0.0)

    logger.info(f"注入期间仪表范围：{lo} ~ {hi}")
    assert hi > 10.0, f"注入未生效，范围 {lo} ~ {hi}"


@pytest.mark.xfail(reason="已知缺陷：Easy 演示工程未做超范围保护", strict=True)
@pytest.mark.regression
def test_meter_protects_against_over_range(canoe):
    """需求：仪表显示应限制在 0~8（0~8000 rpm）

    Easy 演示工程没有范围保护，会显示 12.0 —— 这是【已知缺陷】。
    用 xfail 记录，而不是让它一直红着。
    """
    canoe.set_sysvar("Test", "FaultInject", 1)
    try:
        lo, hi = sample_range(canoe, duration=1.0)
    finally:
        canoe.set_sysvar("Test", "FaultInject", 0)
        canoe.wait_for_sysvar("Engine", "EngineSpeedDspMeter", 0.0)

    logger.info(f"注入期间仪表范围：{lo} ~ {hi}")
    assert hi <= 8.0, f"仪表显示 {hi}，超过物理上限 8.0"
