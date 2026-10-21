# -*- coding: utf-8 -*-
"""
U6：负向测试

正向用例证明"能成功"，负向用例证明"该失败的时候确实失败了"。
测试的价值，一半在负向。

运行：
    python -m pytest uds_tests -v
"""

import pytest
from udsoncan.exceptions import NegativeResponseException
from udsoncan.services import DiagnosticSessionControl

EXTENDED = DiagnosticSessionControl.Session.extendedDiagnosticSession
WRONG_KEY = b"\x00\x00\x00\x00"


def nrc_of(excinfo):
    """从 pytest.raises 的上下文中取出 NRC。"""
    return excinfo.value.response.code


def test_send_key_without_seed_is_rejected(client):
    """没请求种子就发密钥 -> 0x24 顺序错误"""
    client.change_session(EXTENDED)
    with pytest.raises(NegativeResponseException) as exc:
        client.send_key(2, WRONG_KEY)
    assert nrc_of(exc) == 0x24


def test_three_failures_lock_the_ecu(client):
    """连续 3 次错误密钥 -> 35, 35, 36"""
    client.change_session(EXTENDED)
    codes = []
    for _ in range(3):
        client.request_seed(1)
        with pytest.raises(NegativeResponseException) as exc:
            client.send_key(2, WRONG_KEY)
        codes.append(nrc_of(exc))
    assert codes == [0x35, 0x35, 0x36]


def test_retry_during_cooldown_returns_37(client):
    """锁定后立刻重试 -> 0x37 冷却中"""
    client.change_session(EXTENDED)
    for _ in range(3):
        client.request_seed(1)
        with pytest.raises(NegativeResponseException):
            client.send_key(2, WRONG_KEY)

    with pytest.raises(NegativeResponseException) as exc:
        client.request_seed(1)
    assert nrc_of(exc) == 0x37


@pytest.mark.parametrize("session", [0x00, 0x04, 0x7F])
def test_unsupported_session_type_is_rejected(client, session):
    """ECU 只实现 01/02/03，其它合法值一律 0x12"""
    with pytest.raises(NegativeResponseException) as exc:
        client.change_session(session)
    assert nrc_of(exc) == 0x12
