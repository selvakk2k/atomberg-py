# Atomberg Smart Lock Python Library (`atomberg-py`)

A standalone asynchronous Python library for controlling and monitoring Atomberg smart door locks (SL1, SL1 Pro) via Bluetooth Low Energy (BLE), featuring **native zero-snoop pairing**, **cloud key synchronization**, and **public API dynamic PIN generation**.

> **Note on Ceiling Fans**: For Atomberg smart BLDC ceiling fans, please use [`dasshubham762/atomberg-integration`](https://github.com/dasshubham762/atomberg-integration), which is officially recommended by Atomberg in their developer documentation.

## Features

- **Direct Offline BLE Control**: High-speed, local AES-128 encrypted locking, unlocking, and auto-relock tracking.
- **Zero-Snoop Native Pairing**: Directly pairs new or reset locks from Home Assistant or Python without requiring Android Developer Options, ADB, or `btsnoop_hci.log` packet extraction.
- **Cloud Account Key Sync**: For locks already configured in the Atomberg mobile app, automatically imports encryption credentials directly from your Atomberg account.
- **Hardware Audit Logging**: Real-time decoding of unlock credentials (fingerprint slot, keypad PIN used, NFC card, mobile app, and manual thumbturn).
- **Public API Guest PINs**: Generates temporary keypad OTP PINs via Atomberg's public HTTP API.

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

## Credits & License

- Based on reverse-engineering and initial BLE protocol implementation by **[dreadedlama/atomberg-lock](https://github.com/dreadedlama/atomberg-lock)**.
- Licensed under the **GNU General Public License v3.0 (GPL-3.0)**. See [LICENSE](LICENSE) for details.
