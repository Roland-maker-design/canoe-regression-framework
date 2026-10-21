# -*- coding: utf-8 -*-
"""
U6：状态机与时序

两种测法：
    1. 纯状态机单测   —— 不碰 CAN，快、稳、好定位
    2. 总线集成测试   —— 走 udsoncan，验证"整条链路"
"""

import time

import pytest
from udsoncan.exceptions import NegativeResponseException
from udsoncan.services import DiagnosticSessionControl

from u1_session_machine import SessionMachine

EXTENDED = DiagnosticSessionControl.Session.extendedDiagnosticSession


def test_s3_timeout_falls_back_to_default():
    """纯状态机：S3 超时后自动回到 Default，值也变回 01"""
    m = SessionMachine(s3_timeout=0.1)
    m.handle(bytes([0x10, 0x03]))
    time.sleep(0.15)

    resp = m.handle(bytes([0x22, 0xF1, 0x86]))
    assert resp == bytes([0x62, 0xF1, 0x86, 0x01])
    assert m.s3_expired_count == 1


def test_switch_to_default_locks_ecu(client, unlock):
    """切换会话会清掉解锁状态，切回扩展也必须重新解锁"""
    client.change_session(EXTENDED)
    unlock()

    client.change_session(0x01)
    client.change_session(EXTENDED)

    with pytest.raises(NegativeResponseException) as exc:
        client.write_data_by_identifier(0xF1A0, 1)
    assert exc.value.response.code == 0x33


def test_s3_timeout_on_bus(client, ecu):
    """总线集成：把 S3 调短，验证会话真的掉回 Default"""
    old_timeout = ecu.ecu.s3_timeout
    ecu.ecu.s3_timeout = 0.2
    try:
        client.change_session(EXTENDED)
        time.sleep(0.35)

        resp = client.read_data_by_identifier(0xF186)
        assert resp.service_data.values[0xF186][0] == 0x01
    finally:
        ecu.ecu.s3_timeout = old_timeout
