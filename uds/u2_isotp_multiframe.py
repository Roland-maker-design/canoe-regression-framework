# -*- coding: utf-8 -*-
"""
U2：ISO-TP 多帧传输演示

发送三种长度的 UDS 载荷，观察它们在总线上被拆成什么帧：
    7 字节  -> 单帧
    8 字节  -> 首帧 + 连续帧
    20 字节 -> 首帧 + 两条连续帧

注意：isotp.CanStack.send() 只是"入队"，真正发送要靠循环调用 process()。
所以发送端和接收端各开一个 process 线程。
"""

import threading
import time

import can
import isotp

CH = "isotp_demo"
REQ_ID = 0x7E0    # 诊断仪 -> ECU
RESP_ID = 0x7E8   # ECU -> 诊断仪


def fmt(b):
    return bytes(b).hex(" ").upper()


def describe(msg):
    """按 PCI 高 4 位判断帧类型，并给出注释。"""
    d = msg.data
    pci = d[0] >> 4
    n = d[0] & 0x0F

    if pci == 0x0:
        return f"SF  单帧     长度={n}      载荷={fmt(d[1:1 + n])}"
    if pci == 0x1:
        total = (n << 8) | d[1]
        return f"FF  首帧     总长={total:<3d}   前6字节={fmt(d[2:])}"
    if pci == 0x2:
        return f"CF  连续帧   序号={n:<3d}   载荷={fmt(d[1:])}"
    if pci == 0x3:
        state = {0: "继续发", 1: "等一等", 2: "溢出"}.get(n, "?")
        return f"FC  流控     {state}    BS={d[1]}  STmin={d[2]}"
    return "未知帧类型"


def pump(stack, stop):
    """不停地处理收发队列，直到 stop 被设置。"""
    while not stop.is_set():
        stack.process()
        time.sleep(0.001)


def case(name, payload, stack_t, stack_e, observer):
    print(f"\n{'=' * 66}")
    print(f"{name}：UDS 载荷 {len(payload)} 字节 = {fmt(payload)}")
    print("-" * 66)

    stack_t.send(payload)      # 只是入队
    time.sleep(0.3)            # 给两个栈的 process 线程干活的时间

    frames = []
    while True:
        m = observer.recv(timeout=0.05)
        if m is None:
            break
        frames.append(m)

    for m in frames:
        print(f"  0x{m.arbitration_id:03X}  {fmt(m.data):<24} {describe(m)}")

    got = stack_e.recv(timeout=1.0)
    ok = got == payload
    print(f"  → ECU 重组出 {len(got) if got else 0} 字节，与原载荷一致：{ok}")
    return ok


def main():
    bus_t = can.Bus(interface="virtual", channel=CH)
    bus_e = can.Bus(interface="virtual", channel=CH)
    bus_obs = can.Bus(interface="virtual", channel=CH)

    addr_t = isotp.Address(isotp.AddressingMode.Normal_11bits, txid=REQ_ID, rxid=RESP_ID)
    addr_e = isotp.Address(isotp.AddressingMode.Normal_11bits, txid=RESP_ID, rxid=REQ_ID)

    stack_t = isotp.CanStack(bus=bus_t, address=addr_t)
    stack_e = isotp.CanStack(bus=bus_e, address=addr_e)

    stop = threading.Event()
    threads = [
        threading.Thread(target=pump, args=(stack_t, stop), daemon=True),
        threading.Thread(target=pump, args=(stack_e, stop), daemon=True),
    ]
    for t in threads:
        t.start()

    try:
        results = [
            case("单帧边界内", bytes.fromhex("624C5341564155"), stack_t, stack_e, bus_obs),
            case("刚好超过单帧", bytes.fromhex("6210" + "41" * 6), stack_t, stack_e, bus_obs),
            case("读 VIN 的响应", bytes([0x62, 0xF1, 0x90]) + b"LSVAU2180N2183294",
                 stack_t, stack_e, bus_obs),
        ]
        print(f"\n{'=' * 66}")
        print(f"三种长度全部传输成功：{all(results)}")
    finally:
        stop.set()
        for t in threads:
            t.join(timeout=1)
        bus_t.shutdown()
        bus_e.shutdown()
        bus_obs.shutdown()


if __name__ == "__main__":
    main()
