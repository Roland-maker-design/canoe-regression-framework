"""日志模块 —— 控制台彩色输出 + 文件落盘"""
#1.标准库
import logging
import os
from datetime import datetime

#2.三方库
import colorlog

#3.本项目库
from framework.config_loader import load_config

# 本次运行的标记：模块加载时算一次
RUN_TAG = datetime.now().strftime("%Y%m%d_%H%M%S")

# 本次运行的日志文件路径，第一次调用 get_logger 时才确定
_log_file = None

def get_logger(name: str = "canoe", log_dir: str | None = None,
               level: str | None = None) -> logging.Logger:
    """获取一个配置好的 logger"""
    #注册进loggerdict
    logger = logging.getLogger(name)

    # 关键 1：只问"我自己配过没有"，不问别人
    #基础配置流程，避免出现重复打印日志的情况
    if getattr(logger, "_canoe_configured", False):#查找logger的_canoe_configured对象
        return logger

    

    if log_dir is None or level is None:
        _logging_cfg = load_config()["logging"]
        log_dir = log_dir or _logging_cfg["log_dir"]
        level = level or _logging_cfg["level"]

    logger.setLevel(level)#设置输出level级别的日志
    # 关键 2：切断向 root logger 的传播
    logger.propagate = False

    # ---------- Handler A：控制台（带颜色）----------
    #以下为标准的colorlog配置流程
    console = colorlog.StreamHandler()
    console.setFormatter(colorlog.ColoredFormatter(
        "%(log_color)s%(asctime)s [%(levelname)-8s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
        log_colors={"DEBUG": "cyan", "INFO": "green", "WARNING": "yellow",
                    "ERROR": "red", "CRITICAL": "bold_red"},
    ))
    logger.addHandler(console)
    #addhandler往已存在的logger塞handler

    # ---------- Handler B：文件（纯文本）----------
    # ↓↓↓ 填这 4 处 ↓↓↓
    global _log_file

    # TODO 1：第一次调用时，建目录 + 定文件名
    if _log_file is None:
        #这里是创建log_dir目录，如果不存在就创建
        os.makedirs(log_dir, exist_ok=True)
        #用于计算路径用的
        _log_file = os.path.join(log_dir, f"test_{RUN_TAG}.log")

    # TODO 2：创建文件 handler
    file_handler = logging.FileHandler(_log_file,encoding='utf-8')  # ← TODO 2：为什么必须写这个参数？

    # TODO 3：给它挂一个【不带颜色】的格式，因为彩色通过ANSI码实现，写入文件就会有乱码
    #"%(asctime)s [%(levelname)-8s] %(name)s: %(message)s"是不带颜色的格式
    file_handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)-8s] %(name)s: %(message)s"))

    # TODO 4：挂到 logger 上
    logger.addHandler(file_handler)
    # ↑↑↑ 填到这儿 ↑↑↑

    logger._canoe_configured = True
    return logger


def get_log_file():
    """本次运行的日志文件路径"""
    return _log_file

#关于本文件的解释：
#为何很少见到print，因为print和logger走的是不同的输出流，输出时会打架，所以这里一律使用logger