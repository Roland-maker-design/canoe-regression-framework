# -*- coding: utf-8 -*-
"""
U5：udsoncan + pytest 的夹具

和 tests\\conftest.py 的区别：
    tests\\      -> 拉起 CANoe
    uds_tests\\  -> 在虚拟 CAN 上拉起我们自己写的 ECU 模拟器

两者互不干扰，所以 uds_tests 故意不在 pytest.ini 的 testpaths 里。
运行方式：python -m pytest uds_tests -v
"""

import can
import isotp
import pytest
import udsoncan
from udsoncan.client import Client
from udsoncan.connections import PythonIsoTpConnection

from u3_security_access import SecuredEcu, compute_key  # noqa: F401
from u4_ecu_simulator import CanEcu

CHANNEL = "uds_pytest"
REQ_ID = 0x7E0
RESP_ID = 0x7E8

# 告诉 udsoncan 每个 DID 多大、怎么解码
DID_CONFIG = {
    0xF186: udsoncan.DidCodec("B"),    # 当前会话，1 字节
    0xF1A0: udsoncan.DidCodec("B"),    # 自定义 DID，1 字节
    0xF1FF: udsoncan.DidCodec("B"),    # 故意配一个 ECU 不认识的，用来测负向
}


@pytest.fixture(scope="session")
def ecu():
    """整个测试会话只启动一次 ECU 模拟器。"""
    node = CanEcu(channel=CHANNEL, s3_timeout=60)
    node.start()
    yield node
    node.close()


@pytest.fixture(scope="session")
def client(ecu):
    """udsoncan 客户端。CanStack 自带线程，不需要我们写 process 循环。"""
    bus = can.Bus(interface="virtual", channel=CHANNEL)
    stack = isotp.CanStack(
        bus=bus,
        address=isotp.Address(isotp.AddressingMode.Normal_11bits, txid=REQ_ID, rxid=RESP_ID),
    )
    conn = PythonIsoTpConnection(stack)
    config = dict(udsoncan.configs.default_client_config)
    config["data_identifiers"] = DID_CONFIG

    with Client(conn, config=config, request_timeout=2) as c:
        yield c

    bus.shutdown()


@pytest.fixture
def unlock(client):
    """返回一个"解锁"函数，多个测试文件都能用。"""

    def _unlock(level=1):
        seed_resp = client.request_seed(level)
        seed = int.from_bytes(seed_resp.service_data.seed, "big")
        return client.send_key(level + 1, compute_key(seed).to_bytes(4, "big"))

    return _unlock


@pytest.fixture(autouse=True)
def reset_state(ecu, client):
    """每个用例开始前把 ECU 的会话和安全状态都清干净。"""
    # 只切会话不够：失败次数和锁定时间不属于会话，必须单独清
    ecu.ecu.failed_attempts = 0
    ecu.ecu.locked_until = 0.0
    client.change_session(0x01)
    yield
