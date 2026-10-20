"""Tests for cryptographic and CRC routines."""

import pytest
from pyatomberg.const import HSJ_FACTORY_KEY
from pyatomberg.crypto import (
    calculate_modbus_crc16,
    decrypt_aes_ecb,
    encrypt_aes_ecb,
    verify_modbus_crc16,
)
from pyatomberg.exceptions import AtombergCryptoError


def test_modbus_crc16_standard_vector():
    """Verify Modbus CRC-16 with standard ASCII '123456789' vector (0x4B37)."""
    data = b"123456789"
    crc = calculate_modbus_crc16(data)
    assert crc == 0x4B37

    # Appended little-endian
    data_with_crc = data + crc.to_bytes(2, byteorder="little")
    assert verify_modbus_crc16(data_with_crc) is True
    assert verify_modbus_crc16(data + b"\x00\x00") is False


def test_aes_ecb_roundtrip():
    """Verify AES-128-ECB encryption and decryption roundtrip with PKCS7 padding."""
    plaintext = b"AtombergLockTestPayload"
    encrypted = encrypt_aes_ecb(plaintext, HSJ_FACTORY_KEY, pad=True)
    assert encrypted != plaintext
    assert len(encrypted) % 16 == 0

    decrypted = decrypt_aes_ecb(encrypted, HSJ_FACTORY_KEY, unpad=True)
    assert decrypted == plaintext


def test_aes_ecb_exact_block_no_pad():
    """Verify AES-128-ECB encryption and decryption without padding on exact 16-byte block."""
    plaintext = b"1234567890123456"
    encrypted = encrypt_aes_ecb(plaintext, HSJ_FACTORY_KEY, pad=False)
    assert len(encrypted) == 16

    decrypted = decrypt_aes_ecb(encrypted, HSJ_FACTORY_KEY, unpad=False)
    assert decrypted == plaintext


def test_aes_ecb_invalid_key_length():
    """Verify exception raised on invalid key length."""
    with pytest.raises(AtombergCryptoError, match="must be exactly 16 bytes"):
        encrypt_aes_ecb(b"test", b"short_key")

    with pytest.raises(AtombergCryptoError, match="must be exactly 16 bytes"):
        decrypt_aes_ecb(b"1234567890123456", b"short_key")
