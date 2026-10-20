"""Tests for BLE lock pairing and credential extraction."""

import pytest
from pyatomberg.exceptions import AtombergCryptoError, AtombergPairingError
from pyatomberg.lock.pairing import (
    AtombergBLEPairingManager,
    PairingResult,
    extract_keys_from_btsnoop,
)


def test_pairing_result_formatting():
    """Verify PairingResult hex formatting."""
    key = b"\x01" * 16
    salt = b"\x1a\x2b\x3c\x4d"
    result = PairingResult(
        mac_address="AA:BB:CC:DD:EE:FF",
        master_key=key,
        salt=salt,
    )
    assert result.mac_address == "AA:BB:CC:DD:EE:FF"
    assert result.master_key_hex == "01" * 16
    assert result.salt_hex == "1a2b3c4d"


def test_extract_btsnoop_invalid_file(tmp_path):
    """Verify error raised on invalid BTSnoop file header."""
    dummy_file = tmp_path / "invalid.log"
    dummy_file.write_bytes(b"NOT_A_BTSNOOP_FILE")

    with pytest.raises(AtombergCryptoError, match="Invalid BTSnoop file header"):
        extract_keys_from_btsnoop(dummy_file)


@pytest.mark.asyncio
async def test_pairing_manager_custom_key_validation():
    """Verify key and salt length validation during native pairing."""
    manager = AtombergBLEPairingManager()

    with pytest.raises(AtombergPairingError, match="Master key must be exactly 16 bytes"):
        await manager.pair_device("AA:BB:CC:DD:EE:FF", custom_key=b"short_key")

    with pytest.raises(AtombergPairingError, match="Lock salt must be exactly 4 bytes"):
        await manager.pair_device(
            "AA:BB:CC:DD:EE:FF",
            custom_key=b"\x00" * 16,
            custom_salt=b"long_salt_here",
        )
