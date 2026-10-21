# -*- coding: utf-8 -*-
"""
U0 练习：在 python-can 虚拟总线上发出第一帧 UDS 诊断请求。

说明：
- virtual 接口不需要任何硬件，也不需要 CANoe。
- 只要两条 Bus 的 channel 名字相同，它们就在同一根"虚拟总线"上。
- 本脚本里 observer 不是 ECU，只是一个"贴在总线上的记录仪"。
  真正的 ECU 模拟器在 U4 才写。
"""

import time

import can

CHANNEL = "uds_demo"   # 虚拟通道名，随便起，但收发两端必须一致
TX_ID = 0x7E0          # 诊断仪 -> ECU
RX_ID = 0x7E8          # ECU -> 诊断仪

# 三种报文（已经带上 ISO-TP 的单帧长度字节 0x02 / 0x06 / 0x03）
REQ_SESSION = [0x02, 0x3E, 0x00]                    # 请求：进入扩展会话
RESP_POS = [0x06, 0x50, 0x03, 0x00, 0x32]  # 正响应：50 03 + P2/P2*
RESP_NEG = [0x03, 0x7F, 0x3E, 0x12]                 # 负响应：7F 10 22


def hex_str(data):
    """把字节序列格式化成 '02 10 03' 这种可读形式。"""
    return bytes(data).hex(" ").upper()


def describe(data):
    """粗解析一帧：区分 请求 / 正响应 / 负响应，并打印关键字段。"""
    length = data[0] & 0x0F          # ISO-TP 单帧：低 4 位 = 有效载荷长度
    payload = data[1:1 + length]     # 剥掉 PCI 字节，取出真正的 UDS 内容

    if not payload:
        return "空载荷"

    if payload[0] == 0x7F:
        sid = payload[1]
        nrc = payload[2] if len(payload) > 2 else 0
        return f"负响应：7F  被拒 SID=0x{sid:02X}  NRC=0x{nrc:02X}"

    sid = payload[0]
    if sid >= 0x40:
        return f"正响应：SID=0x{sid:02X}（原服务 0x{sid - 0x40:02X} + 0x40）"
    return f"请求：  SID=0x{sid:02X}  参数={payload[1:].hex(' ').upper() or '(无)'}"


def show_frame(direction, can_id, data):
    print(f"[{direction}] 0x{can_id:03X}  {hex_str(data)}")
    print(f"        {describe(data)}")


def main():
    # 1. 开两条虚拟总线
    tester = can.Bus(interface="virtual", channel=CHANNEL)
    observer = can.Bus(interface="virtual", channel=CHANNEL)

    try:
        # 2. 诊断仪发送请求
        req = can.Message(arbitration_id=TX_ID, data=REQ_SESSION, is_extended_id=False)
        t0 = time.perf_counter()
        tester.send(req)

        got = observer.recv(timeout=1.0)
        if got is None:
            print("❌ 1 秒内没收到任何帧 —— 检查通道名是否一致")
            return
        print(f"（接收耗时 {(time.perf_counter() - t0) * 1000:.2f} ms）\n")
        show_frame("RX", got.arbitration_id, got.data)
        print()

        # 3. 模拟 ECU 回一个正响应，看它在总线上长什么样
        pos = can.Message(arbitration_id=RX_ID, data=RESP_POS, is_extended_id=False)
        tester.send(pos)
        got = observer.recv(timeout=1.0)
        show_frame("RX", got.arbitration_id, got.data)
        print()

        # 4. 再模拟一个负响应，对比三种形态
        neg = can.Message(arbitration_id=RX_ID, data=RESP_NEG, is_extended_id=False)
        tester.send(neg)
        got = observer.recv(timeout=1.0)
        show_frame("RX", got.arbitration_id, got.data)
    finally:
        tester.shutdown()
        observer.shutdown()


if __name__ == "__main__":
    main()
