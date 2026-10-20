"""Tests for AtombergClient and fan state synchronization."""

import pytest
from pyatomberg.auth.developer import DeveloperTokenHandler
from pyatomberg.client import AtombergClient
from pyatomberg.exceptions import AtombergAuthError
from pyatomberg.fan.device import AtombergFan


def test_client_init_validation():
    """Verify client rejects initialization without auth."""
    with pytest.raises(AtombergAuthError, match="must be provided"):
        AtombergClient()

    client = AtombergClient(developer_token="sample_dev_token", api_key="sample_api_key")
    assert isinstance(client.auth_handler, DeveloperTokenHandler)
    assert client.auth_handler.refresh_token == "sample_dev_token"
    assert client.auth_handler.api_key == "sample_api_key"


def test_fan_state_update_from_udp():
    """Verify local UDP packet automatically updates fan state."""
    client = AtombergClient(developer_token="token123")
    fan = AtombergFan(
        device_id="ab_fan_room1",
        name="Living Room Fan",
        client=client,
    )
    client.fans["ab_fan_room1"] = fan

    callback_called = False

    def on_fan_change(updated_fan: AtombergFan):
        nonlocal callback_called
        callback_called = True

    fan.register_callback(on_fan_change)

    # Simulate arrival of UDP packet payload
    packet = {
        "device_id": "ab_fan_room1",
        "power": 1,
        "speed": 5,
        "sleep": 1,
        "timer": 2,
    }
    client._handle_udp_state("ab_fan_room1", packet)

    assert fan.state.power is True
    assert fan.state.speed == 5
    assert fan.state.sleep is True
    assert fan.state.timer_hours == 2
    assert callback_called is True
