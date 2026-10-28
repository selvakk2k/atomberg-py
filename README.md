# Atomberg Devices Python Library (`atomberg-py`)

[![Hardware Verified](https://img.shields.io/badge/Hardware-Verified%20(SL1%20Pro)-success.svg)](#features)
[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](LICENSE)
[![PyPI](https://img.shields.io/pypi/v/pyatomberg.svg)](https://pypi.org/project/pyatomberg/)

An asynchronous Python library for authentication, discovery, and control of **Atomberg smart home devices** (smart door locks, smart ceiling fans, and connected appliances).

> [!NOTE]
> **Ceiling Fan Integration**:
> For Home Assistant users seeking control of Atomberg smart ceiling fans, an integration supporting both Cloud and IR control is already available at [`dasshubham762/atomberg-integration`](https://github.com/dasshubham762/atomberg-integration).

---

## Features

- **Universal Authentication Engine**: Native AWS Cognito OAuth2 + PKCE supporting Email, Google, Apple, and Facebook logins, plus official Developer API token management.
- **Multi-Device Discovery**: Discovers and imports paired smart locks, ceiling fans, and connected appliances associated with your Atomberg account.
- **Direct Offline BLE Lock Control**: High-speed, local AES-128 encrypted locking, unlocking, and battery monitoring for SL1 / SL1 Pro smart locks.
- **Offline Dynamic OTP PINs**: Offline algorithmic generation of single-use remote OTPs and expirable timed guest PINs with automatic half-hour boundary quantization.
- **Hardware Audit Logging**: Real-time decoding of credential unlock records (fingerprint slot, NFC card, keypad PIN, or mobile app).
- **Local Fan Protocol**: Asynchronous UDP listener and state tracker for Atomberg Wi-Fi smart fans.

---

## Installation

```bash
pip install pyatomberg
```

For development:
```bash
git clone https://github.com/selvakk2k/atomberg-py.git
cd atomberg-py
python -m venv .venv
source .venv/bin/activate  # Or .venv\Scripts\activate on Windows
pip install -e ".[dev]"
```

---

## Quick Start: Smart Lock (BLE)

```python
import asyncio
from pyatomberg.lock import AtombergLock

async def main():
    lock = AtombergLock(
        mac_address="AA:BB:CC:11:22:33",
        master_key=b"0123456789abcdef",
        salt=bytes.fromhex("1a2b3c4d"),
    )
    await lock.connect()
    await lock.authenticate()
    print(f"Battery: {await lock.get_battery()}%")
    await lock.unlock()
    await lock.disconnect()

asyncio.run(main())
```

---

## Quick Start: Remote & Timed Guest OTPs

```python
import asyncio
from pyatomberg.lock import AtombergDynamicPinClient

async def main():
    client = AtombergDynamicPinClient(
        api_key="your_api_key",
        access_token="your_access_token",
    )

    # 1. Immediate single-use Remote OTP (valid for 15 minutes, spent upon unlock)
    remote_otp = await client.generate_remote_otp(device_id="your_device_id")
    print(f"One-Time Code: {remote_otp['otp']}")

    # 2. Timed OTP (valid for 4 hours, expires automatically)
    timed_otp = await client.generate_timed_otp(device_id="your_device_id", duration_hours=4.0)
    print(f"Timed Code: {timed_otp['otp']}, Expires: {timed_otp['expires_at']}")

asyncio.run(main())
```

---

## Credits & License

- Based on reverse-engineering and initial BLE protocol implementation by **[dreadedlama/atomberg-lock](https://github.com/dreadedlama/atomberg-lock)**.
- Licensed under the **GNU General Public License v3.0 (GPL-3.0)**. See [LICENSE](LICENSE) for details.
