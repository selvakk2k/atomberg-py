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


@pytest.mark.asyncio
async def test_cloud_sync_parsing():
    """Verify AtombergCloudSync correctly parses production app_open response."""
    from unittest.mock import AsyncMock, MagicMock
    from pyatomberg.lock.cloud_sync import AtombergCloudSync

    mock_resp_data = {
        "status": "Success",
        "message": {
            "user_details": {
                "families": [
                    {
                        "family_id": "test_fam_1",
                        "devices": [
                            {
                                "device_id": "63c9c483b94a",
                                "friendly_name": "Entrance Lock",
                                "model": "smart_lock_black",
                                "metadata": {
                                    "adminAuthCode": "00A00EC9",
                                    "aes": "AgABfsR33DdoSdMe",
                                    "bleProtocolVersion": "32",
                                    "description": "Smart Lock",
                                    "generalAuthCode": "482B2C89",
                                    "lockMac": "63c9c483b94a",
                                    "tempAuthCode": "04820A68",
                                },
                            }
                        ],
                    }
                ]
            }
        },
    }

    mock_response = MagicMock()
    mock_response.status = 200
    mock_response.json = AsyncMock(return_value=mock_resp_data)

    mock_session = MagicMock()
    mock_session.closed = False
    mock_session.get.return_value.__aenter__ = AsyncMock(return_value=mock_response)
    mock_session.get.return_value.__aexit__ = AsyncMock(return_value=None)

    client = AtombergCloudSync(access_token="test_access_token", session=mock_session)
    locks = await client.fetch_account_locks()

    assert len(locks) == 1
    lock = locks[0]
    assert lock.mac_address == "63:C9:C4:83:B9:4A"
    assert lock.name == "Entrance Lock"
    assert lock.model == "smart_lock_black"
    assert lock.master_key == b"AgABfsR33DdoSdMe"
    assert lock.salt == bytes.fromhex("00A00EC9")
