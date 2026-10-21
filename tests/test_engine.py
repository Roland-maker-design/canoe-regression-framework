"""
发动机 / 车灯相关测试用例

注意：这个文件里【没有任何运行器代码】——
     没有 for 循环、没有 try/except、没有 print 结果。
     pytest 会自动找到所有 test_ 开头的函数并执行。

     你上节课手写的那个运行器，pytest 全帮你做了。
"""
import pytest
from pytest import approx

pytestmark = pytest.mark.regression      # ← 整个文件都打成 regression，也就是在文件范围内每个函数前面加@pytest.mark.regression


# ======================================================================
# 测试用例
# ======================================================================
def test_initial_speed_is_zero(canoe):
    """初始状态：仪表显示转速应该是 0"""

    actual = canoe.get_sysvar("Engine", "EngineSpeedDspMeter")
    assert actual == approx(0.0), f"初始转速应为 0.0，实际为 {actual}"


def test_engine_speed_1000(canoe):
    """点火 + 油门 1000 rpm → 仪表显示 1.0"""
    canoe.set_sysvar("Engine", "EngineStateSwitch", 1)
    canoe.set_sysvar("Engine", "EngineSpeedEntry", 1000.0)

    ok, waited = canoe.wait_for_sysvar("Engine", "EngineSpeedDspMeter", 1.0)
    actual = canoe.get_sysvar("Engine", "EngineSpeedDspMeter")

    assert ok, f"等待超时（{waited:.2f}s），当前值 {actual}"
    assert actual == approx(1.0), f"期望 1.0，实际 {actual}"


def test_engine_speed_2500(canoe):
    """点火 + 油门 2500 rpm → 仪表显示 2.5"""

    canoe.set_sysvar("Engine", "EngineStateSwitch", 1)
    canoe.set_sysvar("Engine", "EngineSpeedEntry", 2500.0)

    ok, waited = canoe.wait_for_sysvar("Engine", "EngineSpeedDspMeter", 2.5)
    actual = canoe.get_sysvar("Engine", "EngineSpeedDspMeter")

    assert ok, f"等待超时（{waited:.2f}s），当前值 {actual}"
    assert actual == 2.5, f"期望 2.5，实际 {actual}"


def test_engine_off_clears_speed(canoe):
    """先给转速，再关点火 → 转速应该归零"""

    canoe.set_sysvar("Engine", "EngineStateSwitch", 1)
    canoe.set_sysvar("Engine", "EngineSpeedEntry", 3000.0)
    canoe.wait_for_sysvar("Engine", "EngineSpeedDspMeter", 3.0)

    canoe.set_sysvar("Engine", "EngineStateSwitch", 0)
    ok, waited = canoe.wait_for_sysvar("Engine", "EngineSpeedDspMeter", 0.0)

    assert ok, f"关点火后转速未归零（等了 {waited:.2f}s）"


def test_hazard_light_display(canoe):
    """踩下危险灯开关 → LightDisplay 应该是 3"""

    canoe.set_sysvar("Lights", "HazardLightsSwitch", 1)
    ok, waited = canoe.wait_for_sysvar("Lights", "LightDisplay", 3)

    actual = canoe.get_sysvar("Lights", "LightDisplay")
    assert ok, f"等待超时（{waited:.2f}s），LightDisplay = {actual}"
