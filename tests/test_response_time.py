"""
响应时间测试 —— 从施加激励到输出稳定的耗时

参数化和刚才一样，但断言的对象从「值对不对」变成了「快不快」。
"""

import pytest
import pytest
from pytest import approx

pytestmark = pytest.mark.regression      # ← 整个文件都打成 regression，也就是在文件范围内每个函数前面加@pytest.mark.regression


RESPONSE_CASES = [
    pytest.param(500.0,  0.5, id="500rpm"),
    pytest.param(2500.0, 2.5, id="2500rpm"),
    pytest.param(3500.0, 3.5, id="3500rpm"),
]

@pytest.mark.parametrize("rpm, expected_display", RESPONSE_CASES)
def test_response_time(canoe, cfg, rpm, expected_display):        # ← 加 cfg
    """从设置输入到仪表更新，应在配置的上限内完成"""
    max_ms = cfg["thresholds"]["max_response_ms"]                 # ← 从配置读

    canoe.set_sysvar("Engine", "EngineStateSwitch", 1)
    canoe.set_sysvar("Engine", "EngineSpeedEntry", rpm)

    ok, waited = canoe.wait_for_sysvar(
        "Engine", "EngineSpeedDspMeter", expected_display
    )
    elapsed_ms = waited * 1000

    assert ok, f"超时未达到 {expected_display}"
    assert elapsed_ms < max_ms, (
        f"响应 {elapsed_ms:.0f}ms 超过上限 {max_ms}ms"
        f"（理论最坏 100ms × 2 倍安全系数）"
    )