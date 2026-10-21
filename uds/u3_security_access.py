# -*- coding: utf-8 -*-
"""
U3：0x27 安全访问（种子 + 密钥）

流程：
    27 01              -> 67 01 + seed（4 字节）
    [诊断仪用 seed 算出 key]
    27 02 + key        -> 67 02（成功）/ 7F 27 35（密钥错）

在 U1 的会话状态机基础上扩展：
    - 未解锁时，0x2E 写数据 -> 7F 2E 33
    - 解锁后，0x2E 写数据   -> 6E F1 A0
"""

import time

from u1_session_machine import (
    S_DEFAULT,
    S_EXTENDED,
    SESSION_NAMES,
    SessionMachine,
    fmt,
    negative,
)

# ---------- 额外的 NRC ----------
NRC_REQUEST_SEQUENCE_ERROR = 0x24
NRC_SECURITY_ACCESS_DENIED = 0x33
NRC_INVALID_KEY = 0x35
NRC_EXCEEDED_ATTEMPTS = 0x36
NRC_REQUIRED_DELAY = 0x37

# 演示用的“机密”。真实项目里这个值不会出现在你的代码里，
# 密钥算法通常放在 CDD/ODX 或厂家提供的安全插件中。
SECRET = 0x12345678
DEMO_SEED = 0x1A2B3C4D


def compute_key(seed):
    """演示用密钥算法：异或 + 32 位循环左移 13 位。

    真实 ECU 常用 AES、RSA，或厂家私有算法，且每次种子不同。
    """
    x = seed ^ SECRET
    return ((x << 13) | (x >> 19)) & 0xFFFFFFFF


class SecuredEcu(SessionMachine):
    """在会话状态机上，加上安全访问。"""

    def __init__(self, s3_timeout=5.0, max_attempts=3, lock_seconds=3.0):
        super().__init__(s3_timeout=s3_timeout)
        self.unlocked = False
        self.seed_pending = False
        self.current_seed = 0
        self.failed_attempts = 0
        self.max_attempts = max_attempts
        self.lock_seconds = lock_seconds
        self.locked_until = 0.0

    # ---------- 会话变化时，安全状态也要跟着变 ----------
    def _check_s3(self):
        before = self.session
        super()._check_s3()
        if before != S_DEFAULT and self.session == S_DEFAULT:
            self.unlocked = False
            self.seed_pending = False

    def _session_control(self, req):
        resp = super()._session_control(req)
        if resp[0] != 0x7F:          # 会话切换成功
            self.unlocked = False
            self.seed_pending = False
        return resp

    # ---------- 写数据前先检查解锁 ----------
    def _write_did(self, req):
        if self.session != S_EXTENDED:
            return negative(0x2E, 0x7F)
        if not self.unlocked:
            return negative(0x2E, NRC_SECURITY_ACCESS_DENIED)
        return super()._write_did(req)

    # ---------- 0x27 ----------
    def handle(self, request):
        if request[0] == 0x27:
            self._check_s3()
            self.last_request = time.monotonic()
            return self._security_access(request)
        return super().handle(request)

    def _security_access(self, req):
        # 1. 会话检查
        if self.session != S_EXTENDED:
            return negative(0x27, 0x7F)

        # 2. 冷却检查（尝试次数超限后）
        if time.monotonic() < self.locked_until:
            return negative(0x27, NRC_REQUIRED_DELAY)

        # 3. 长度检查
        if len(req) < 2:
            return negative(0x27, 0x13)

        sub = req[1] & 0x7F

        # 4. 奇数 = 请求种子
        if sub % 2 == 1:
            if sub != 0x01:
                return negative(0x27, 0x12)
            if self.unlocked:
                # 已解锁时，标准规定返回全 0 种子
                return bytes([0x67, sub, 0x00, 0x00, 0x00, 0x00])
            self.seed_pending = True
            self.current_seed = DEMO_SEED
            return bytes([0x67, sub]) + self.current_seed.to_bytes(4, "big")

        # 5. 偶数 = 发送密钥
        if sub != 0x02:
            return negative(0x27, 0x12)

        if not self.seed_pending:
            return negative(0x27, NRC_REQUEST_SEQUENCE_ERROR)

        if len(req) < 6:
            return negative(0x27, 0x13)

        key = int.from_bytes(req[2:6], "big")
        if key == compute_key(self.current_seed):
            self.unlocked = True
            self.seed_pending = False
            self.failed_attempts = 0
            return bytes([0x67, sub])

        # 密钥错误
        self.failed_attempts += 1
        if self.failed_attempts >= self.max_attempts:
            self.locked_until = time.monotonic() + self.lock_seconds
            self.failed_attempts = 0
            return negative(0x27, NRC_EXCEEDED_ATTEMPTS)
        return negative(0x27, NRC_INVALID_KEY)


def show(m, req):
    resp = m.handle(req)
    state = SESSION_NAMES[m.session] + ("，已解锁" if m.unlocked else "，未解锁")
    print(f"  请求 {fmt(req):<22} -> 响应 {fmt(resp):<26} [{state}]")
    return resp


def main():
    print("正确的密钥（用种子算出来）：")
    print(f"  seed = 0x{DEMO_SEED:08X}")
    print(f"  key  = 0x{compute_key(DEMO_SEED):08X}")
    good_key = compute_key(DEMO_SEED).to_bytes(4, "big")

    m = SecuredEcu(s3_timeout=60)

    print("\n=== 1. 没解锁就写数据 ===")
    show(m, bytes([0x10, 0x03]))                       # 进扩展会话
    show(m, bytes([0x2E, 0xF1, 0xA0, 0x01]))           # 7F 2E 33

    print("\n=== 1.5 没请求种子就发密钥 ===")
    show(m, bytes([0x27, 0x02, 0x2C, 0xC2, 0xE8, 0x0E]))

    print("\n=== 2. 请求种子 ===")
    show(m, bytes([0x27, 0x01]))                       # 67 01 1A 2B 3C 4D

    print("\n=== 3. 发一个错误密钥 ===")
    show(m, bytes([0x27, 0x02, 0x00, 0x00, 0x00, 0x00]))   # 7F 27 35

    print("\n=== 4. 发正确密钥，再写数据 ===")
    show(m, bytes([0x27, 0x02]) + good_key)            # 67 02
    show(m, bytes([0x2E, 0xF1, 0xA0, 0x01]))           # 6E F1 A0

    print("\n=== 5. 已解锁时再请求种子 ===")
    show(m, bytes([0x27, 0x01]))                       # 67 01 00 00 00 00

    print("\n=== 6. 切回默认会话 -> 自动上锁 ===")
    show(m, bytes([0x10, 0x01]))
    show(m, bytes([0x10, 0x03]))
    show(m, bytes([0x2E, 0xF1, 0xA0, 0x01]))           # 又是 7F 2E 33

    print("\n=== 7. 连续 3 次错误密钥 -> 锁定 ===")
    m2 = SecuredEcu(s3_timeout=60, max_attempts=3, lock_seconds=3.0)
    m2.handle(bytes([0x10, 0x03]))
    for i in range(3):
        m2.handle(bytes([0x27, 0x01]))
        resp = m2.handle(bytes([0x27, 0x02, 0x00, 0x00, 0x00, 0x00]))
        print(f"  第 {i + 1} 次错误 -> {fmt(resp)}")

    print("\n=== 8. 锁定期间再试 ===")
    show(m2, bytes([0x27, 0x01]))                      # 7F 27 37
    print("  等待冷却结束...")
    time.sleep(3.1)
    show(m2, bytes([0x27, 0x01]))                      # 又能拿到种子了


if __name__ == "__main__":
    main()
