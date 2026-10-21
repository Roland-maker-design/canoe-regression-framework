"""冒烟测试 —— 确认框架本身能跑起来

这个文件不是测被测系统的，是测【你的框架】的。
以后每次改完框架，先跑它。
"""
import pytest


@pytest.mark.smoke
def test_canoe_is_connected(canoe):
    """CANoe 连上了，而且打开的是 Easy 工程"""
    assert canoe.config_name() == "Easy"


@pytest.mark.smoke
def test_measurement_is_running(canoe):
    """测量正在跑"""
    assert canoe.is_running() is True


@pytest.mark.smoke
def test_initial_state(canoe):
    """复位之后，仪表转速应该是 0"""
    assert canoe.get_sysvar("Engine", "EngineSpeedDspMeter") == 0.0