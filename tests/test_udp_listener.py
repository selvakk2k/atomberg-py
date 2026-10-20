"""Tests for UDP datagram listener and parser."""

from pyatomberg.fan.udp_listener import parse_fan_datagram


def test_parse_haproxy_prefixed_datagram():
    """Verify parsing of PROXY TCP4 prefixed datagrams."""
    raw = (
        b"PROXY TCP4 192.168.1.55 192.168.1.1 5625 5625\r\n"
        b'{"device_id":"ab_fan_test123","power":1,"speed":4,"sleep":0,"timer":0,"last_seen":1728723456}'
    )
    result = parse_fan_datagram(raw)
    assert result is not None
    device_id, payload = result
    assert device_id == "ab_fan_test123"
    assert payload["power"] == 1
    assert payload["speed"] == 4
    assert payload["sleep"] == 0
    assert payload["timer"] == 0


def test_parse_pure_json_datagram():
    """Verify parsing of direct JSON UDP datagrams."""
    raw = b'{"device_id":"ab_fan_purejson","power":0,"speed":0}'
    result = parse_fan_datagram(raw)
    assert result is not None
    device_id, payload = result
    assert device_id == "ab_fan_purejson"
    assert payload["power"] == 0
    assert payload["speed"] == 0


def test_parse_invalid_datagram():
    """Verify invalid datagrams return None without raising exceptions."""
    assert parse_fan_datagram(b"NOT_A_VALID_DATAGRAM") is None
    assert parse_fan_datagram(b"") is None
    assert parse_fan_datagram(b'{"no_id_here": 123}') is None
