"""配置加载模块 —— 把散落的魔法数字集中到 config/test_config.yaml"""

from pathlib import Path

import yaml

# ★ 项目根目录 = 这个文件自己的上上级
#   本文件在 <项目根>\framework\config_loader.py
#Path(__file__)代表的当前脚本的绝对路径，.resolve()是规范化，去../.；统一分隔符，解析软链，.parent是取上级目录
PROJECT_ROOT = Path(__file__).resolve().parent.parent      # ← TODO 1：几层 .parent？

# 默认配置文件位置（用 / 拼接，Path 会自己处理平台差异）
#等价于PROJECT_ROOT.joinpath("config", "test_config.yaml")事后会组合成./config/test_config.yaml
DEFAULT_CONFIG = PROJECT_ROOT / "config" / "test_config.yaml"

#path=None代表这个参数可传也可不传，->dict是预期为返回一个dict类型的return
def load_config(path=None) -> dict:
    """读取 YAML 配置

    参数:
        path: 配置文件路径。省略时用默认的 config/test_config.yaml

    返回:
        dict，键名和 YAML 层级一一对应
    """
    if path is None:
        path = DEFAULT_CONFIG
    else:
        path = Path(path)
        # 传进来的是相对路径 → 以【项目根】为基准，而不是 cwd
        #path.is_absolute()检测是否为绝对路径，这里带not为检测是否为相对路径
        if not path.is_absolute():
            path = PROJECT_ROOT / path
    #encoding='utf-8'是确定格式，避免乱码
    with open(path, encoding='utf-8') as f:     # ← TODO 2：为什么必须写这个参数？
        #safe_load只可以使用基本类型，相对安全
        return yaml.safe_load(f)                  # ← TODO 3：safe_load 还是 unsafe_load？


def resolve_path(p) -> Path:
    """把配置里写的相对路径，解析成绝对路径（以项目根为基准）

    配置里写 "configs/Easy/Easy.cfg"，不管你在哪启动程序，
    都会解析成 <项目根>\\configs\\Easy\\Easy.cfg
    """
    p = Path(p)
    if p.is_absolute():
        return p
    return PROJECT_ROOT / p                              # ← TODO 4：相对路径怎么拼？