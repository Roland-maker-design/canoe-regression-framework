"""CANoe 控制器 —— 把 COM 细节全封在这里"""

import time

import win32com.client as win32

from framework.config_loader import load_config
from framework.logger import get_logger

logger = get_logger()#获取yaml配置，注册进logger


class CanoeController:  #因为PEP8要求定义之间要隔两个空行
    """CANoe 遥控器"""

    def __init__(self, visible=None):
        """连接 CANoe。

        如果 CANoe 还没运行，Dispatch 会自动把它启动起来（实测约 7 秒）；
        如果已经在运行，则瞬间"附着"上去。
        """
        self.cfg=load_config()#读取yaml配置文件
        self.timeouts = self.cfg["timeouts"]#读取yaml配置文件中的timeout配置
        if visible is None:
            visible = self.cfg["canoe"]["visible"]#读取yaml配置文件中的canoe配置
        logger.info("正在连接CANoe...")
        t0 = time.time()#开始计时
        self.app = win32.Dispatch("CANoe.Application")
        self.app.Visible = visible
        elapsed = time.time() - t0#结束计时，并将时间存在elapsed变量中
        logger.info(f"已连接，耗时{elapsed:.1f}s")#elapsed来源于上一行的时间计算变量

    # ------------------------------------------------------------------
    # 工程（Configuration）
    # ------------------------------------------------------------------
    def open_config(self, path):
        """打开一个 .cfg 工程文件"""
        logger.info(f"打开工程：{path}")
        self.app.Open(path)

    def config_name(self):
        """当前工程名（没打开工程时是空字符串）"""
        return self.app.Configuration.Name

    def config_path(self):
        """当前工程的完整路径"""
        return self.app.Configuration.FullName

    def config_is_modified(self):
        """检查是否有未保存的改动"""
        return self.app.Configuration.Modified

    # ------------------------------------------------------------------
    # 测量（Measurement）
    # ------------------------------------------------------------------
    def is_running(self):
        """当前是否正在测量 —— 返回 True / False"""
        return self.app.Measurement.Running

    def wait_until_running(self, expected=True, timeout=None):
        """等 Measurement.Running 变成期望值

        参数:
            expected: True 表示等它跑起来，False 表示等它停下来
            timeout:  省略时用配置里的 timeouts.measurement

        返回:
            True = 等到了；False = 超时了还没变

        为什么要这个方法:
            实测过 Measurement.Start() 返回 ≠ 测量真的跑起来了，
            Running 属性有约 50ms 延迟 —— 必须【轮询等待】状态真正改变。
        """
        if timeout is None:
            timeout = self.timeouts["measurement"]

        t0 = time.time()
        while time.time() - t0 < timeout:
            if self.is_running() == expected:
                return True
            time.sleep(self.timeouts["poll_interval"])
        return False

    def start_measurement(self, timeout=None):
        """开始测量"""
        if timeout is None:
            timeout = self.timeouts["measurement"]

        if self.is_running():
            logger.debug("测量已运行，跳过")
            return

        t0 = time.time()
        self.app.Measurement.Start()
        if not self.wait_until_running(expected=True, timeout=timeout):
            raise RuntimeError(f"等待测量启动超时（{timeout}s）")
        logger.info(f"测量已开始（耗时 {time.time() - t0:.2f}s）")

    def stop_measurement(self, timeout=None):
        """停止测量（幂等：本来没跑就跳过）"""
        if timeout is None:
            timeout = self.timeouts["measurement"]

        if not self.is_running():
            logger.debug("测量本来就没在运行，跳过")
            return

        t0 = time.time()
        self.app.Measurement.Stop()
        if not self.wait_until_running(expected=False, timeout=timeout):
            raise RuntimeError(f"等待测量停止超时（{timeout}s）")
        logger.info(f"测量已停止（耗时 {time.time() - t0:.2f}s）")

    def restart_measurement(self):
        """先停用再开始，重启测量"""
        logger.info("重启测量")
        self.stop_measurement()
        self.start_measurement()

    # ------------------------------------------------------------------
    # 系统变量 —— Python 与 CANoe 之间的数据通道
    # ------------------------------------------------------------------
    def get_sysvar(self, namespace, name):
        """读一个系统变量的值"""
        return self.app.System.Namespaces(namespace).Variables(name).Value

    def set_sysvar(self, namespace, name, value):
        """写一个系统变量的值

        注意：值的类型必须和变量类型一致！
              float 型变量（如 EngineSpeedEntry）必须传 2500.0，不能传 2500。
        """
        self.app.System.Namespaces(namespace).Variables(name).Value = value

    def wait_for_sysvar(self, namespace, name, expected,
                        timeout=None, interval=None):
        """轮询等待系统变量变为期望值

        参数:
            namespace: 系统变量的命名空间，如 "Engine"
            name:      变量名，如 "EngineSpeedDspMeter"
            expected:  期望的值
            timeout:   省略时用配置里的 timeouts.sysvar
            interval:  省略时用配置里的 timeouts.poll_interval

        返回:
            (是否成功, 实际等待秒数)
        """
        if timeout is None:
            timeout = self.timeouts["sysvar"]
        if interval is None:
            interval = self.timeouts["poll_interval"]

        t0 = time.time()
        while time.time() - t0 < timeout:
            if self.get_sysvar(namespace, name) == expected:
                return True, time.time() - t0
            time.sleep(interval)
        return False, time.time() - t0

    # ------------------------------------------------------------------
    # 收工
    # ------------------------------------------------------------------
    
    def quit(self):
        """关闭 CANoe"""
        logger.info("CANoe 已关闭")
        self.app.Quit()