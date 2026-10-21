# -*- coding: utf-8 -*-
"""
U3 练习：12 条有序请求，预测每条的响应。

用法：
1. 先别运行
2. 用四步法 + 安全状态预测，填在纸上
3. 再运行对账

提示：这一组只考三件事
    - 会话（Default / Extended）
    - 解锁状态（unlocked）
    - 0x27 的顺序（种子 -> 密钥）
"""

from u3_security_access import DEMO_SEED, SecuredEcu, compute_key
from u1_session_machine import SESSION_NAMES, fmt

# 注意：密钥依赖 u3_security_access.py 里的 SECRET，
# 所以这里动态计算，而不是写死。
KEY = compute_key(DEMO_SEED).to_bytes(4, "big")

SEQUENCE = [
    ("27 01", bytes([0x27, 0x01])),                          # 1
    ("10 03", bytes([0x10, 0x03])),                          # 2
    ("27 02 + key（未请求种子）", bytes([0x27, 0x02]) + KEY),   # 3
    ("2E F1 A0 01", bytes([0x2E, 0xF1, 0xA0, 0x01])),        # 4
    ("27 01", bytes([0x27, 0x01])),                          # 5
    ("27 02 + 错误key", bytes([0x27, 0x02, 0, 0, 0, 0])),    # 6
    ("27 02 + 正确key", bytes([0x27, 0x02]) + KEY),           # 7
    ("2E F1 A0 01", bytes([0x2E, 0xF1, 0xA0, 0x01])),        # 8
    ("27 01", bytes([0x27, 0x01])),                          # 9
    ("10 01", bytes([0x10, 0x01])),                          # 10
    ("10 03", bytes([0x10, 0x03])),                          # 11
    ("2E F1 A0 01", bytes([0x2E, 0xF1, 0xA0, 0x01])),        # 12
]


def main():
    m = SecuredEcu(s3_timeout=60)

    print(f"本次 SECRET 对应的 key = {fmt(KEY)}\n")
    print(f"{'#':>2}  {'请求':<24} {'响应':<26} 状态")
    print("-" * 78)
    for i, (label, req) in enumerate(SEQUENCE, 1):
        resp = m.handle(req)
        state = SESSION_NAMES[m.session] + ("，已解锁" if m.unlocked else "，未解锁")
        print(f"{i:2d}  {label:<24} {fmt(resp):<26} {state}")


if __name__ == "__main__":
    main()
