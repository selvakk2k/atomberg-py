# Atomberg Devices Python Library (`atomberg-py`)

[![Hardware Verified](https://img.shields.io/badge/Hardware-Verified%20(SL1%20Pro)-success.svg)](#features)
[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](LICENSE)
[![PyPI](https://img.shields.io/pypi/v/pyatomberg.svg)](https://pypi.org/project/pyatomberg/)

An asynchronous Python library for controlling and monitoring **Atomberg smart door locks** (SL1, SL1 Pro) via Bluetooth Low Energy (BLE) and **Atomberg smart ceiling fans** over local network UDP.

> **Home Assistant Users**:
> For the ready-to-use Home Assistant custom integration, see **[`ha-atomberg-lock`](https://github.com/selvakk2k/ha-atomberg-lock)**.
> For offline local IR control of Atomberg ceiling fans, see **[`ha-bldc-fan-ir`](https://github.com/selvakk2k/ha-bldc-fan-ir)**.

---

## Features

- **Direct Offline BLE Control**: High-speed, local AES-128 encrypted locking, unlocking, and battery monitoring.
- **Universal Cognito OAuth2 + PKCE**: Imports registered lock encryption credentials directly from your Atomberg account via AWS Cognito Hosted UI (Email, Google, Apple, or Facebook).
- **Hardware Audit Logging**: Real-time decoding of credential unlock records (fingerprint slot, NFC card, keypad PIN, or mobile app).
- **Remote & Timed OTP Keypad PINs**: Generates single-use remote OTPs and expirable timed guest PINs via Atomberg's dynamic PIN API.
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
- Companion Home Assistant custom component: **[`ha-atomberg-lock`](https://github.com/selvakk2k/ha-atomberg-lock)**.
- Licensed under the **GNU General Public License v3.0 (GPL-3.0)**. See [LICENSE](LICENSE) for details.
