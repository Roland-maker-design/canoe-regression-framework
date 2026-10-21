# -*- coding: utf-8 -*-
"""
U5：用 udsoncan 当诊断仪

前面我们自己写了 Tester 类，手动拼 22 F1 86、27 01 这些字节。
这一节换成 udsoncan：
    你调用 read_data_by_identifier(0xF186)
    udsoncan 负责拼字节、发请求、解析响应、抛 NRC 异常
"""

import can
import isotp
import udsoncan
from udsoncan.client import Client
from udsoncan.connections import PythonIsoTpConnection
from udsoncan.exceptions import NegativeResponseException
from udsoncan.services import DiagnosticSessionControl

from u3_security_access import DEMO_SEED, compute_key
from u4_ecu_simulator import CanEcu

CHANNEL = "udsoncan_demo"
REQ_ID = 0x7E0
RESP_ID = 0x7E8


def main():
    # 1. 启动陪练：ECU 模拟器
    ecu = CanEcu(channel=CHANNEL, s3_timeout=60)
    ecu.start()

    # 2. 诊断仪这一侧：CanStack 自带线程，不需要我们再写 process 循环
    #    注意：CanStack 是 TransportLayer 的子类，udsoncan 打开连接时会自己 start()
    bus = can.Bus(interface="virtual", channel=CHANNEL)
    stack = isotp.CanStack(
        bus=bus,
        address=isotp.Address(isotp.AddressingMode.Normal_11bits, txid=REQ_ID, rxid=RESP_ID),
    )

    # 3. 用 udsoncan 的 Client 包住这个栈
    conn = PythonIsoTpConnection(stack)

    config = dict(udsoncan.configs.default_client_config)
    config["data_identifiers"] = {
        0xF186: udsoncan.DidCodec("B"),    # 1 字节：当前会话
        0xF1A0: udsoncan.DidCodec("B"),    # 1 字节：自定义 DID
    }

    with Client(conn, config=config, request_timeout=2) as client:
        print("=== 1. 切换会话 ===")
        resp = client.change_session(DiagnosticSessionControl.Session.extendedDiagnosticSession)
        print(f"  正响应: {resp.positive}, 会话回显 = 0x{resp.service_data.session_echo:02X}")
        print(f"  P2 = {resp.service_data.p2_server_max} s, P2* = {resp.service_data.p2_star_server_max} s")

        print("\n=== 2. 读 DID 0xF186 ===")
        resp = client.read_data_by_identifier(0xF186)
        # DidCodec("B") 解出来是元组，例如 (3,)
        value = resp.service_data.values[0xF186][0]
        print(f"  数据: 0x{value:02X}（当前会话）")

        print("\n=== 3. 未解锁就写 DID（应该失败）===")
        try:
            client.write_data_by_identifier(0xF1A0, 1)
            print("  !! 不该成功")
        except NegativeResponseException as e:
            # e.response.service 是服务类，不是数字；用 __name__ 打印
            print(f"  被拒: 服务={e.response.service.__name__}, "
                  f"NRC=0x{e.response.code:02X} ({e.response.code_name})")

        print("\n=== 4. 安全访问 ===")
        seed_resp = client.request_seed(1)
        seed = seed_resp.service_data.seed
        print(f"  种子: {seed.hex(' ').upper()}")

        key = compute_key(int.from_bytes(seed, "big")).to_bytes(4, "big")
        key_resp = client.send_key(2, key)
        print(f"  密钥 {key.hex(' ').upper()} -> 正响应: {key_resp.positive}")

        print("\n=== 5. 解锁后再写 DID ===")
        resp = client.write_data_by_identifier(0xF1A0, 1)
        print(f"  正响应: {resp.positive}, DID = 0x{resp.service_data.did_echo:04X}")

        print("\n=== 6. 心跳 ===")
        resp = client.tester_present()
        print(f"  正响应: {resp.positive}")

    # 7. 收尾
    bus.shutdown()
    ecu.close()


if __name__ == "__main__":
    main()
