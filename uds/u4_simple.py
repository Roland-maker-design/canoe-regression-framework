# -*- coding: utf-8 -*-
"""
U4 简化版：不用线程，一步一步地走

目的：先看清楚"一条请求怎么变成一条响应"，再去看多线程版本。

这里一切都是串行的：
    诊断仪发 -> 总线上出现帧 -> ECU 收 -> ECU 处理 -> ECU 回 -> 诊断仪收
每一步都是你眼皮底下发生的，没有线程抢着跑。
"""

import time

import can
import isotp

from u1_session_machine import fmt
from u3_security_access import DEMO_SEED, SecuredEcu, compute_key

CHANNEL = "simple_ecu"
REQ_ID = 0x7E0
RESP_ID = 0x7E8


def main():
    # 两条总线实例，接在同一个虚拟通道上
    bus_t = can.Bus(interface="virtual", channel=CHANNEL)
    bus_e = can.Bus(interface="virtual", channel=CHANNEL)

    # 诊断仪：发到 0x7E0，听 0x7E8
    stack_t = isotp.CanStack(
        bus=bus_t,
        address=isotp.Address(isotp.AddressingMode.Normal_11bits, txid=REQ_ID, rxid=RESP_ID),
    )
    # ECU：发到 0x7E8，听 0x7E0
    stack_e = isotp.CanStack(
        bus=bus_e,
        address=isotp.Address(isotp.AddressingMode.Normal_11bits, txid=RESP_ID, rxid=REQ_ID),
    )

    # ECU 的大脑：会话机 + 安全访问
    ecu = SecuredEcu(s3_timeout=60)

    def exchange(payload, timeout=1.0):
        """一次完整的"问 - 答"，全程串行，每一步都看得见。"""
        print(f"\n  诊断仪 发送 : {fmt(payload)}")
        stack_t.send(bytes(payload))          # 1. 放进诊断仪的发送队列

        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            stack_t.process()                 # 2. 两边各自收发一点
            stack_e.process()

            req = stack_e.recv()              # 3. ECU 收到完整请求了吗？
            if req is not None:
                print(f"  ECU   收到 : {fmt(req)}")
                resp = ecu.handle(bytes(req))  # 4. 大脑处理
                print(f"  ECU   回复 : {fmt(resp)}")
                stack_e.send(resp)             # 5. 放进 ECU 的发送队列

            ans = stack_t.recv()              # 6. 诊断仪收到响应了吗？
            if ans is not None:
                print(f"  诊断仪 收到 : {fmt(ans)}")
                return bytes(ans)

            time.sleep(0.001)

        print("  !! 超时")
        return None

    key = compute_key(DEMO_SEED).to_bytes(4, "big")

    print("=" * 66)
    print("第 1 次：10 03 —— 进入扩展会话")
    print("=" * 66)
    exchange(bytes([0x10, 0x03]))

    print("\n" + "=" * 66)
    print("第 2 次：2E F1 A0 01 —— 还没解锁就想写")
    print("=" * 66)
    exchange(bytes([0x2E, 0xF1, 0xA0, 0x01]))

    print("\n" + "=" * 66)
    print("第 3 次：27 01 + 27 02 —— 解锁")
    print("=" * 66)
    exchange(bytes([0x27, 0x01]))
    exchange(bytes([0x27, 0x02]) + key)

    print("\n" + "=" * 66)
    print("第 4 次：2E F1 A0 01 —— 解锁后再写")
    print("=" * 66)
    exchange(bytes([0x2E, 0xF1, 0xA0, 0x01]))

    bus_t.shutdown()
    bus_e.shutdown()


if __name__ == "__main__":
    main()
