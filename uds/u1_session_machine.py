# -*- coding: utf-8 -*-
"""
U1：会话状态机 + S3 超时 + NRC 的最小演示

特点：
- 纯 Python，不碰 CAN，不碰 ISO-TP
- 输入/输出都是"UDS 层"的字节（不含 PCI 长度字节）
- 这份状态机在 U4 会被装进 ECU 模拟器里，所以现在写得像样一点
"""

import time

# ---------- 会话常量 ----------
S_DEFAULT = 0x01
S_PROGRAMMING = 0x02
S_EXTENDED = 0x03

SESSION_NAMES = {
    S_DEFAULT: "Default",
    S_PROGRAMMING: "Programming",
    S_EXTENDED: "Extended",
}

# ---------- 会用到的 NRC ----------
NRC_SERVICE_NOT_SUPPORTED = 0x11
NRC_SUBFUNCTION_NOT_SUPPORTED = 0x12
NRC_INCORRECT_LENGTH = 0x13
NRC_REQUEST_OUT_OF_RANGE = 0x31
NRC_SERVICE_NOT_SUPPORTED_IN_SESSION = 0x7F


def fmt(b):
    """把字节序列打印成 '50 03 00 32' 这种样子。"""
    return bytes(b).hex(" ").upper()


def negative(sid, nrc):
    """构造负响应：7F + 被拒的 SID + NRC"""
    return bytes([0x7F, sid, nrc])


def add_pci(payload):
    """加上 ISO-TP 单帧 PCI，并补 0 到 8 字节（仅用于打印展示）。"""
    assert len(payload) <= 7, "超过 7 字节就要用多帧，U2 再讲"
    return bytes([len(payload)]) + payload + bytes(7 - len(payload))


class SessionMachine:
    """最小会话状态机：只管 0x10 / 0x3E / 0x22 / 0x2E 四个服务。"""

    def __init__(self, s3_timeout=5.0):
        self.session = S_DEFAULT
        self.s3_timeout = s3_timeout
        self.last_request = time.monotonic()
        self.s3_expired_count = 0

    def _check_s3(self):
        """每次处理请求前，先检查会话是否已经超时掉线。"""
        if self.session == S_DEFAULT:
            return
        if time.monotonic() - self.last_request > self.s3_timeout:
            old = self.session
            self.session = S_DEFAULT
            self.s3_expired_count += 1
            print(f"  [S3] 超时！{SESSION_NAMES[old]} -> Default"
                  f"（{self.s3_timeout} 秒内没有任何请求）")

    def handle(self, request):
        """处理一条 UDS 请求，返回 UDS 响应（都不含 PCI）。"""
        self._check_s3()
        self.last_request = time.monotonic()

        sid = request[0]
        if sid == 0x10:
            return self._session_control(request)
        if sid == 0x3E:
            return self._tester_present(request)
        if sid == 0x22:
            return self._read_did(request)
        if sid == 0x2E:
            return self._write_did(request)
        return negative(sid, NRC_SERVICE_NOT_SUPPORTED)

    # ---------- 0x10 ----------
    def _session_control(self, req):
        if len(req) < 2:
            return negative(0x10, NRC_INCORRECT_LENGTH)

        sub = req[1] & 0x7F          # 最高位是 suppressPosRsp，先忽略
        if sub not in (S_DEFAULT, S_PROGRAMMING, S_EXTENDED):
            return negative(0x10, NRC_SUBFUNCTION_NOT_SUPPORTED)

        self.session = sub
        # 正响应：50 + 子功能 + P2(2字节) + P2*(2字节)
        return bytes([0x50, sub, 0x00, 0x32, 0x01, 0xF4])

    # ---------- 0x3E ----------
    def _tester_present(self, req):
        if len(req) < 2:
            return negative(0x3E, NRC_INCORRECT_LENGTH)

        sub = req[1] & 0x7F
        if sub != 0x00:
            return negative(0x3E, NRC_SUBFUNCTION_NOT_SUPPORTED)

        return bytes([0x7E, 0x00])

    # ---------- 0x22 ----------
    def _read_did(self, req):
        if len(req) < 3:
            return negative(0x22, NRC_INCORRECT_LENGTH)

        did = (req[1] << 8) | req[2]
        if did == 0xF186:                       # DID = 当前会话
            return bytes([0x62, 0xF1, 0x86, self.session])
        if did == 0xF190:                       # DID = VIN
            return bytes([0x62, 0xF1, 0x90]) + b"LSVAU2180N2183294"
        return negative(0x22, NRC_REQUEST_OUT_OF_RANGE)

    # ---------- 0x2E ----------
    def _write_did(self, req):
        # 0x2E 只在扩展会话允许 —— 专门用来演示 NRC 0x7F
        if self.session != S_EXTENDED:
            return negative(0x2E, NRC_SERVICE_NOT_SUPPORTED_IN_SESSION)

        if len(req) < 4:                        # 2E + DID(2) + 至少 1 字节数据 = 4
            return negative(0x2E, NRC_INCORRECT_LENGTH)

        did = (req[1] << 8) | req[2]
        if did != 0xF1A0:                       # 自定义 DID，示例用
            return negative(0x2E, NRC_REQUEST_OUT_OF_RANGE)

        return bytes([0x6E]) + req[1:3]


def show(machine, req):
    resp = machine.handle(req)
    print(f"  请求 {fmt(req):<18} -> 响应 {fmt(resp):<22} 会话={SESSION_NAMES[machine.session]}")
    print(f"       总线上: {fmt(add_pci(resp))}")


def main():
    # 把 S3 故意调成 0.3 秒：标准是 5 秒，但我们不需要等那么久
    m = SessionMachine(s3_timeout=0.3)

    print("=== 1. 默认会话下的请求 ===")
    show(m, bytes([0x3E, 0x00]))                 # 心跳 -> 7E 00
    show(m, bytes([0x22, 0xF1, 0x86]))           # 读会话 -> 62 F1 86 01
    show(m, bytes([0x2E, 0xF1, 0xA0, 0x01]))     # 默认会话写数据 -> 7F 2E 7F

    print("\n=== 2. 进入扩展会话 ===")
    show(m, bytes([0x10, 0x03]))                 # -> 50 03 00 32 01 F4
    show(m, bytes([0x2E, 0xF1, 0xA0, 0x01]))     # -> 6E F1 A0

    print("\n=== 3. 非法 / 越界请求 ===")
    show(m, bytes([0x99, 0x00]))                 # 不支持的服务 -> 7F 99 11
    show(m, bytes([0x10, 0x04]))                 # 不支持的子功能 -> 7F 10 12
    show(m, bytes([0x22, 0xF1, 0xFF]))           # 不存在的 DID   -> 7F 22 31

    print("\n=== 4. S3 超时 ===")
    print(f"  等待 {m.s3_timeout + 0.1:.1f} 秒，期间不发任何请求...")
    time.sleep(m.s3_timeout + 0.1)
    show(m, bytes([0x22, 0xF1, 0x86]))           # 应该已经掉回 Default
    print("\n=== 5. 心跳续命 ===")
    m.handle(bytes([0x10, 0x03]))                # 重新进扩展会话
    for i in range(3):
        time.sleep(m.s3_timeout * 0.7)           # 每次间隔 0.21s < 0.3s
        m.handle(bytes([0x3E, 0x00]))            # 发心跳
        print(f"  第 {i+1} 次心跳后，会话 = {SESSION_NAMES[m.session]}")
    print(f"  心跳后超时次数 = {m.s3_expired_count}（应该还是 1）")
    print(f"\n  S3 超时次数 = {m.s3_expired_count}")


if __name__ == "__main__":
    main()
