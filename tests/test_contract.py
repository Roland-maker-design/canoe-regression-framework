"""
契约测试（Contract Test）—— 验证「外部系统的行为符合我们的假设」

为什么要测这个？
    我们的框架依赖一个假设：「测量没在跑时，Stop() 会抛异常」。
    如果哪天 CANoe 升级改了这个行为，我们希望【立刻知道】，
    而不是等到某个莫名其妙的 bug 出现才发现。
"""

import pytest
from pytest import approx

pytestmark = pytest.mark.regression      # ← 整个文件都打成 regression，也就是在文件范围内每个函数前面加@pytest.mark.regression
import pywintypes


def test_stop_when_not_running_raises(canoe):
    """测量没在跑时调用 Stop()，CANoe 应该拒绝并抛异常"""
    # 先确保测量是停止状态
    if canoe.is_running():
        canoe.stop_measurement()

    # pytest.raises：断言「这段代码应该抛出指定类型的异常」
    with pytest.raises(pywintypes.com_error):
        canoe.app.Measurement.Stop()


def test_stop_when_running_succeeds(canoe):
    """测量正在跑时调用 Stop()，应该正常成功"""
    if not canoe.is_running():
        canoe.start_measurement()

    canoe.stop_measurement()

    assert not canoe.is_running(), "调用 Stop 之后，测量应该已经停止"


def test_start_twice_is_safe(canoe):
    """重复 Start 不应该崩（我们的 start_measurement 有保护）"""
    canoe.start_measurement()
    canoe.start_measurement()      # 第二次：应该被保护逻辑拦住，不抛异常

    assert canoe.is_running()
