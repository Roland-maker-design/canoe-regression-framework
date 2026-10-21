# -*- coding: utf-8 -*-
"""
U1 练习：一串有序请求，预测每条的响应。

用法：
1. 先别运行本脚本
2. 打开 UDS笔记.txt 的【十二】四步法，逐条预测，写在纸上
3. 再运行本脚本对账

规则：会话状态会随请求变化，必须按顺序一条一条来。
"""

from u1_session_machine import SESSION_NAMES, SessionMachine, fmt

# 注意：这里的顺序就是发送顺序，不能打乱
SEQUENCE = [
    "22 F1 86",       # 1
    "2E F1 A0 01",    # 2
    "10 03",          # 3
    "22 F1 86",       # 4
    "2E F1 A0 01",    # 5
    "2E F1 B0 01",    # 6
    "2E F1 A0",       # 7
    "10 04",          # 8
    "3E 00",          # 9
    "99 00",          # 10
    "22 F1 FF",       # 11
    "10 01",          # 12
    "22 F1 86",       # 13
    "3E",             # 14
    "2E F1 A0",       # 15
    "10 83",          # 16
]


def main():
    m = SessionMachine(s3_timeout=60)   # 调大 S3，避免做题中途会话掉线

    print(f"{'#':>2}  {'请求':<14} {'响应':<22} 会话")
    print("-" * 60)
    for i, text in enumerate(SEQUENCE, 1):
        req = bytes.fromhex(text.replace(" ", ""))
        resp = m.handle(req)
        print(f"{i:2d}  {text:<14} {fmt(resp):<22} {SESSION_NAMES[m.session]}")


if __name__ == "__main__":
    main()
