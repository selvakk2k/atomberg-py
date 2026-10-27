"""Tests for Atomberg dynamic PIN and OTP generation."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock
import pytest

from pyatomberg.exceptions import AtombergConnectionError
from pyatomberg.lock.dynamic_pin import AtombergDynamicPinClient


@pytest.mark.asyncio
async def test_generate_remote_otp() -> None:
    """Test generating an immediate single-use Remote OTP."""
    mock_response = MagicMock()
    mock_response.status = 200
    mock_response.json = AsyncMock(return_value={
        "status": True,
        "message": {
            "data": {
                "pin": "583921",
                "device_id": "test_lock_123",
            }
        }
    })

    mock_session = MagicMock()
    mock_session.closed = False
    mock_session.post.return_value.__aenter__ = AsyncMock(return_value=mock_response)
    mock_session.post.return_value.__aexit__ = AsyncMock(return_value=None)

    pin_client = AtombergDynamicPinClient(
        api_key="test_api_key",
        access_token="test_access_token",
        session=mock_session,
    )

    result = await pin_client.generate_remote_otp(
        device_id="test_lock_123",
        arrival_window_minutes=15,
    )

    assert result["otp"] == "583921"
    assert result["type"] == "remote_one_time"
    assert result["device_id"] == "test_lock_123"
    assert result["expires_at"] > result["created_at"]
    assert mock_session.post.called


@pytest.mark.asyncio
async def test_generate_timed_otp() -> None:
    """Test generating a single-use Timed OTP with custom duration."""
    mock_response = MagicMock()
    mock_response.status = 200
    mock_response.json = AsyncMock(return_value={
        "status": True,
        "message": {
            "data": {
                "dynamic_pin": "992144",
                "device_id": "test_lock_456",
            }
        }
    })

    mock_session = MagicMock()
    mock_session.closed = False
    mock_session.post.return_value.__aenter__ = AsyncMock(return_value=mock_response)
    mock_session.post.return_value.__aexit__ = AsyncMock(return_value=None)

    pin_client = AtombergDynamicPinClient(
        api_key="test_api_key",
        access_token="test_access_token",
        session=mock_session,
    )

    result = await pin_client.generate_timed_otp(
        device_id="test_lock_456",
        duration_hours=4.0,
        start_time=1700000000,
    )

    assert result["otp"] == "992144"
    assert result["type"] == "timed"
    assert result["device_id"] == "test_lock_456"
    assert result["created_at"] == 1700000000
    assert result["expires_at"] == 1700000000 + (4 * 3600)
    assert result["duration_hours"] == 4.0


@pytest.mark.asyncio
async def test_generate_otp_api_failure() -> None:
    """Test handling of API error response."""
    mock_response = MagicMock()
    mock_response.status = 400
    mock_response.json = AsyncMock(return_value={
        "status": False,
        "message": "Device not found or not in pairing mode",
    })

    mock_session = MagicMock()
    mock_session.closed = False
    mock_session.post.return_value.__aenter__ = AsyncMock(return_value=mock_response)
    mock_session.post.return_value.__aexit__ = AsyncMock(return_value=None)

    pin_client = AtombergDynamicPinClient(
        api_key="test_api_key",
        access_token="test_access_token",
        session=mock_session,
    )

    with pytest.raises(AtombergConnectionError, match="Failed to generate lock PIN"):
        await pin_client.generate_remote_otp(device_id="invalid_lock")
