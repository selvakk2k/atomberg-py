"""Tests for offline lock credential extraction and pairing results."""

import pytest
from pyatomberg.exceptions import AtombergCryptoError, AtombergPairingError
from pyatomberg.lock.pairing import (
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


def test_extract_btsnoop_file_not_found():
    """Verify FileNotFoundError when log file does not exist."""
    with pytest.raises(FileNotFoundError):
        extract_keys_from_btsnoop("non_existent_file.btsnoop")
