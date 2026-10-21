# -*- coding: utf-8 -*-
"""
U4：最小 ECU 模拟器 —— 把状态机接到 CAN 总线上

架构：

    诊断仪 stack (0x7E0 -> 0x7E8)
         ↕  虚拟 CAN 总线
    ECU stack    (0x7E8 -> 0x7E0)
         ↕  ISO-TP 拆包
    SecuredEcu.handle()  ← U1 会话机 + U3 安全访问

ECU 的主循环只做三件事：
    1. process()      收发 CAN 帧，重组 ISO-TP
    2. recv()         拿到一条完整请求
    3. handle()+send() 处理并回复
"""

import threading
import time

import can
import isotp

from u1_session_machine import fmt
from u3_security_access import DEMO_SEED, SecuredEcu, compute_key

CHANNEL = "ecu_sim"
REQ_ID = 0x7E0    # 诊断仪 -> ECU
RESP_ID = 0x7E8   # ECU -> 诊断仪


class CanEcu:
    """跑在 CAN 总线上的 ECU 模拟器。"""

    def __init__(self, channel=CHANNEL, s3_timeout=5.0):
        self.bus = can.Bus(interface="virtual", channel=channel)
        addr = isotp.Address(isotp.AddressingMode.Normal_11bits, txid=RESP_ID, rxid=REQ_ID)
        self.stack = isotp.CanStack(bus=self.bus, address=addr)
        self.ecu = SecuredEcu(s3_timeout=s3_timeout)
        self.stop = threading.Event()
        self.thread = threading.Thread(target=self._run, daemon=True)

    def start(self):
        self.thread.start()

    def _run(self):
        last_tick = 0.0
        while not self.stop.is_set():
            self.stack.process()

            req = self.stack.recv()
            if req is not None:
                resp = self.ecu.handle(bytes(req))
                print(f"  [ECU] RX {fmt(req):<22} -> TX {fmt(resp)}")
                self.stack.send(resp)

            # ECU 内部也要定期检查 S3，不能只在收到请求时检查
            now = time.monotonic()
            if now - last_tick > 0.1:
                self.ecu._check_s3()
                last_tick = now

            time.sleep(0.001)

    def close(self):
        self.stop.set()
        self.thread.join(timeout=1)
        self.bus.shutdown()


class Tester:
    """诊断仪：发请求、等响应。"""

    def __init__(self, channel=CHANNEL):
        self.bus = can.Bus(interface="virtual", channel=channel)
        addr = isotp.Address(isotp.AddressingMode.Normal_11bits, txid=REQ_ID, rxid=RESP_ID)
        self.stack = isotp.CanStack(bus=self.bus, address=addr)
        self.stop = threading.Event()
        self.thread = threading.Thread(target=self._pump, daemon=True)

    def start(self):
        self.thread.start()

    def _pump(self):
        while not self.stop.is_set():
            self.stack.process()
            time.sleep(0.001)

    def request(self, payload, timeout=2.0):
        self.stack.send(bytes(payload))       # 入队
        # 注意：block=False（默认）时 timeout 参数会被忽略，必须显式 block=True
        return self.stack.recv(block=True, timeout=timeout)

    def close(self):
        self.stop.set()
        self.thread.join(timeout=1)
        self.bus.shutdown()


def main():
    # 演示把 S3 调成 1 秒，否则要等 5 秒；真实值是 5000ms
    ecu = CanEcu(s3_timeout=1.0)
    tester = Tester()
    ecu.start()
    tester.start()
    time.sleep(0.2)

    key = compute_key(DEMO_SEED).to_bytes(4, "big")

    sequence = [
        ("10 03 进入扩展会话", bytes([0x10, 0x03])),
        ("2E 写数据（未解锁）", bytes([0x2E, 0xF1, 0xA0, 0x01])),
        ("27 01 请求种子", bytes([0x27, 0x01])),
        ("27 02 + 正确密钥", bytes([0x27, 0x02]) + key),
        ("2E 写数据（已解锁）", bytes([0x2E, 0xF1, 0xA0, 0x01])),
        ("22 F1 86 读会话", bytes([0x22, 0xF1, 0x86])),
        ("3E 00 心跳", bytes([0x3E, 0x00])),
        ("22 F1 90 读 VIN", bytes([0x22, 0xF1, 0x90])),
    ]

    print("=== 1. 正常交互 ===")
    for label, req in sequence:
        resp = tester.request(req)
        text = fmt(resp) if resp is not None else "超时"
        print(f"  请求 {label:<22} -> 响应 {text}")
        time.sleep(0.05)

    print("\n=== 2. 等 S3 超时（演示设为 1 秒）===")
    time.sleep(1.3)
    resp = tester.request(bytes([0x22, 0xF1, 0x86]))
    print(f"  请求 22 F1 86（超时后）     -> 响应 {fmt(resp)}   （会话已回到 Default）")

    print("\n=== 3. 会话切换后自动上锁 ===")
    tester.request(bytes([0x10, 0x03]))
    resp = tester.request(bytes([0x2E, 0xF1, 0xA0, 0x01]))
    print(f"  请求 2E F1 A0 01           -> 响应 {fmt(resp)}   （需要重新解锁）")

    tester.close()
    ecu.close()


if __name__ == "__main__":
    main()
