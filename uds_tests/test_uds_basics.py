# -*- coding: utf-8 -*-
"""
U5：第一批 UDS 诊断自动化用例

运行：
    python -m pytest uds_tests -v
"""

import pytest
from udsoncan.exceptions import NegativeResponseException
from udsoncan.services import DiagnosticSessionControl

from u3_security_access import DEMO_SEED, compute_key

EXTENDED = DiagnosticSessionControl.Session.extendedDiagnosticSession


def unlock(client, level=1):
    """请求种子 -> 算密钥 -> 发送密钥，返回 send_key 的响应。"""
    seed_resp = client.request_seed(level)
    seed = int.from_bytes(seed_resp.service_data.seed, "big")
    key = compute_key(seed).to_bytes(4, "big")
    return client.send_key(level + 1, key)


def test_change_session_enters_extended(client):
    resp = client.change_session(EXTENDED)
    assert resp.positive
    assert resp.service_data.session_echo == EXTENDED


def test_read_current_session(client):
    client.change_session(EXTENDED)
    resp = client.read_data_by_identifier(0xF186)
    assert resp.service_data.values[0xF186][0] == EXTENDED


def test_read_unknown_did_is_rejected(client):
    with pytest.raises(NegativeResponseException) as exc:
        client.read_data_by_identifier(0xF1FF)
    assert exc.value.response.code == 0x31


def test_write_without_unlock_is_denied(client):
    client.change_session(EXTENDED)
    with pytest.raises(NegativeResponseException) as exc:
        client.write_data_by_identifier(0xF1A0, 1)
    assert exc.value.response.code == 0x33


def test_unlock_then_write_succeeds(client):
    client.change_session(EXTENDED)
    unlock_resp = unlock(client)
    assert unlock_resp.positive

    resp = client.write_data_by_identifier(0xF1A0, 1)
    assert resp.positive
    assert resp.service_data.did_echo == 0xF1A0


def test_security_access_returns_seed(client):
    client.change_session(EXTENDED)
    resp = client.request_seed(1)
    assert resp.positive
    assert len(resp.service_data.seed) == 4


def test_tester_present(client):
    resp = client.tester_present()
    assert resp.positive

def test_security_access_in_default_session_is_rejected(client):
    with pytest.raises(NegativeResponseException) as exc:
        client.request_seed(1)
    assert exc.value.response.code == 0x7F

def test_wrong_key_is_rejected(client):
    client.change_session(EXTENDED)
    client.request_seed(1)
    with pytest.raises(NegativeResponseException) as exc:
        client.send_key(2, b"\x00\x00\x00\x00")
    assert exc.value.response.code == 0x35