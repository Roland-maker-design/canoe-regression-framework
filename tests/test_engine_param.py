"""
第 4 节 · 第 2 讲：参数化测试

核心思想：把「测试数据」和「测试逻辑」分开。
         逻辑只写一遍，数据写成一张表。
         往表里加一行 = 多一个测试用例。
"""

import pytest
from pytest import approx

pytestmark = pytest.mark.regression      # ← 整个文件都打成 regression，也就是在文件范围内每个函数前面加@pytest.mark.regression

# ======================================================================
# 【数据表】转速 → 仪表应显示的值
#
#   想加测试点？往这张表里加一行就行，不用写新函数。
#   pytest.param(..., id="xxx") 可以给每组数据起个名字，报告里更好看。
# ======================================================================
SPEED_CASES = [
    pytest.param(500.0, 0.5, id="500rpm"),
    pytest.param(1000.0, 1.0, id="1000rpm"),
    pytest.param(1500.0,1.5,id="1500rpm"),
    pytest.param(2500.0, 2.5, id="2500rpm"),
    pytest.param(3000.0,3.0,id="3000rpm"),
    pytest.param(3500.0, 3.5, id="3500rpm"),
]


# ======================================================================
# 【测试逻辑】只写一遍
#
#   @pytest.mark.parametrize("参数名1, 参数名2", 数据表)
#       第一个参数是「参数名的字符串」，必须和函数签名里的名字对上
#       第二个参数是「数据表」
#
#   注意：这里不用写 reset() —— conftest.py 里有个 autouse fixture 自动做
# ======================================================================
@pytest.mark.parametrize("rpm, expected_display", SPEED_CASES)
def test_engine_speed(canoe, rpm, expected_display):
    """点火 + 设定转速 → 仪表显示值应符合预期"""
    canoe.set_sysvar("Engine", "EngineStateSwitch", 1)
    canoe.set_sysvar("Engine", "EngineSpeedEntry", rpm)

    ok, waited = canoe.wait_for_sysvar(
        "Engine", "EngineSpeedDspMeter", expected_display
    )
    actual = canoe.get_sysvar("Engine", "EngineSpeedDspMeter")

    assert ok, f"等待超时（{waited:.2f}s），当前值 {actual}"
    assert actual == expected_display, (
        f"输入 {rpm} rpm，期望显示 {expected_display}，实际 {actual}"
    )


# ======================================================================
# 【另一张表】危险灯开关 → LightDisplay 应显示的值
#   注意：这个用例的参数名和上面的完全无关，各写各的
# ======================================================================
LIGHT_CASES = [
    pytest.param(0, 0, id="hazard-off"),
    pytest.param(1, 3, id="hazard-on"),
]


@pytest.mark.parametrize("switch, expected_display", LIGHT_CASES)
def test_hazard_light(canoe, switch, expected_display):
    """危险灯开关 → LightDisplay 应符合预期"""
    canoe.set_sysvar("Lights", "HazardLightsSwitch", switch)

    ok, waited = canoe.wait_for_sysvar("Lights", "LightDisplay", expected_display)
    actual = canoe.get_sysvar("Lights", "LightDisplay")

    assert ok, f"等待超时（{waited:.2f}s），当前值 {actual}"
    assert actual == expected_display, (
        f"开关={switch}，期望 LightDisplay={expected_display}，实际 {actual}"
    )
