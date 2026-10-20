# Project Handover: Atomberg IoT Python Library & Integration (`atomberg-py`)

This document serves as the primary technical context, reverse-engineered protocol reference, and architectural briefing for any developer or AI coding agent working on the `atomberg-py` repository and its companion Home Assistant custom integration.

---

## Table of Contents

- [1. Executive Summary & Project Scope](#1-executive-summary--project-scope)
- [2. Reverse-Engineering Dossier (`com.atomberg.app` v7.7.2)](#2-reverse-engineering-dossier-comatombergapp-v772)
- [3. Smart Fans Protocol & Architecture](#3-smart-fans-protocol--architecture)
- [4. Smart Locks Protocol: Haosj (HSJ) BLE](#4-smart-locks-protocol-haosj-hsj-ble)
- [5. Smart Locks Protocol: Gecko / Sitana Wi-Fi](#5-smart-locks-protocol-gecko--sitana-wi-fi)
- [6. Extended Device Models: Purifiers & Cooktops](#6-extended-device-models-purifiers--cooktops)
- [7. Hardware Provenance & Ecosystem Analysis](#7-hardware-provenance--ecosystem-analysis)
- [8. Target Library Architecture (`pyatomberg`)](#8-target-library-architecture-pyatomberg)
- [9. Hardware Resumption Checklist & Action Plan](#9-hardware-resumption-checklist--action-plan)

---

## 1. Executive Summary & Project Scope

* **Repository Goal**: Build a unified, standalone Python library (`pyatomberg`) and subsequent Home Assistant custom integration (`atomberg`) supporting Atomberg's ecosystem of smart home devices.
* **Target Devices**:
  1. **Smart BLDC Ceiling Fans**: Renesa, Renesa+, Aris, Erica, Studio+ (Cloud REST + Local Subnet UDP 5625).
  2. **Smart Door Locks**: 
     - **SL1 / SL1 Pro**: Offline Bluetooth Low Energy (BLE) control via Haosj (HSJ) protocol with AES-128 encryption.
     - **SL1.0 / Azhero Series**: Wi-Fi enabled mortise lock using Silicon Labs Wireless Gecko + Firebase Firestore.
  3. **Smart Water Purifiers**: W-Series / W4 (TDS sensors, filter life, tank levels, UV/RO state).
  4. **Smart Cooktops**: Induction cooktop models (Power, heat levels, timer, child lock).
* **Architecture Philosophy**: Local-first wherever possible. Fans use real-time local UDP broadcast listening (port 5625) to eliminate cloud polling latency; locks communicate via direct local Bluetooth Low Energy (`bleak`). Cloud APIs are utilized for initial discovery, token issuance, and non-local fan commands.

---

## 2. Reverse-Engineering Dossier (`com.atomberg.app` v7.7.2)

The official Atomberg Home Android application (`com.atomberg.app` v7.7.2, build 263) was decompiled and analyzed from native assembly (`libapp.so`).

### A. Application Stack & AWS Authentication
* **Framework**: Flutter / Dart compiled into ARMv7/ARM64 shared libraries (`libapp.so`).
* **Authentication Provider**: AWS Amplify + AWS Cognito Identity Provider.
  - **Cognito User Pool ID**: `ap-south-1_fMZyKIlR2`
  - **App Client ID**: `3cr9rf3urr1jvpn46fsd377uv0`
  - **AWS Region**: `ap-south-1` (Mumbai, India)
  - **OAuth Web Domain**: `auth.atomberg-iot.com`
* **Local Mobile Persistence**: Hive DB (`TypeAdapter`s for `SitanaLock`, `LockKey`, `GeckoLock`, `AtomDevice`).

### B. Core Cloud Endpoints (`server.atomberg-iot.com`)
All authenticated mobile app requests communicate with the primary API cluster:

| Endpoint | Method | Purpose |
| :--- | :---: | :--- |
| `https://server.atomberg-iot.com/app_open` | `POST` | Core discovery: returns full device tree (`Fan`, `Lock`, `WaterPurifier`, `Cooktop`, `AtomFamily`) |
| `https://server.atomberg-iot.com/app_open/guest` | `POST` | Unauthenticated discovery mode (fans only; locks explicitly barred) |
| `https://server.atomberg-iot.com/update_device_state/lock` | `POST` | Syncs lock registration metadata and parameters |
| `https://server.atomberg-iot.com/update_device_state/lockhistory` | `POST` | Uploads/syncs hardware audit log events |
| `https://server.atomberg-iot.com/update_device_state/sitanakey/add` | `POST` | Registers new PIN, NFC, or Fingerprint credential in cloud |
| `https://server.atomberg-iot.com/update_device_state/sitanakey/modify` | `POST` | Modifies credential attributes (name, validity, schedule) |
| `https://server.atomberg-iot.com/update_device_state/sitanakey/delete` | `POST` | Revokes credential from cloud inventory |
| `https://server.atomberg-iot.com/update_device_state/sitanaunlock/decision` | `POST` | Confirms remote unlock request approval/rejection |
| `https://server.atomberg-iot.com/update_device_state/lockcommands` | `POST` | Dispatches pending remote commands to Wi-Fi locks |
| `https://server.atomberg-iot.com/update_device_state/w4_state_update` | `POST` | Telemetry sync for W4 water purifiers |
| `https://server.atomberg-iot.com/send_mqtt_to_device` | `POST` | Cloud relay to dispatch MQTT packets to fans/devices |
| `https://server.atomberg-iot.com/lrp/get_dynamic_password` | `POST` | Generates time-synchronized offline keypad OTPs |
| `wss://server.atomberg-iot.com` | `WSS` | WebSocket stream for live mobile client state sync |

---

## 3. Smart Fans Protocol & Architecture

Atomberg smart ceiling fans operate using a hybrid **Cloud Command + Local Subnet Telemetry** architecture.

### A. Official Developer API (`api.developer.atomberg-iot.com`)
* **Portal**: `https://developer.atomberg-iot.com`
* **In-App Activation**: In `com.atomberg.app`, opening `DeveloperOptionsScreen` (`pages/developer_options.dart`) calls:
  `POST https://acw6qw6wsd.execute-api.ap-south-1.amazonaws.com/dev/get_developer_refresh_token`
  *Requirement: At least one Wi-Fi connected fan must be associated with the account.*
* **Endpoints**:
  - `POST /v1/get_access_token`: Exchanging developer `refresh_token` for bearer JWT `access_token`.
  - `GET /v1/get_all_devices`: Retrieves registered fans, models, series, and online status.
  - `POST /v1/send_command`: Dispatches fan controls:
    ```json
    {
      "device_id": "ab_fan_xxxxxxxxxxxx",
      "command": {
        "power": true,
        "speed": 5,
        "sleep": false,
        "timer_hours": 0,
        "light_mode": "daylight",
        "led": 80
      }
    }
    ```

### B. Real-Time Local UDP Broadcast (Port 5625)
* **Mechanics**: Each Wi-Fi canopy module broadcasts unencrypted UDP state datagrams to the local network broadcast address (`255.255.255.255:5625`).
* **Frame Structure**: Uses HAProxy-style text prefixing:
  ```text
  PROXY TCP4 <device_local_ip> <gateway_ip> <src_port> <dst_port>\r\n
  {"device_id":"ab_fan_xxx","power":1,"speed":4,"sleep":0,"timer":0,"last_seen":1728723456}
  ```
* **Integration Strategy**: `pyatomberg` runs an async `UDPListener` on port 5625. When state packets arrive, the library updates the device entity immediately, providing zero-latency state synchronization without querying cloud servers.

---

## 4. Smart Locks Protocol: Haosj (HSJ) BLE

Tested on **Atomberg SL1 / SL1 Pro Smart Door Lock**.

### A. BLE GATT Profile
* **Primary Service UUID**: `0000fff0-0000-1000-8000-00805f9b34fb`
* **Write Characteristic UUID**: `0000fff1-0000-1000-8000-00805f9b34fb` (Write / Write without response)
* **Notify Characteristic UUID**: `0000fff2-0000-1000-8000-00805f9b34fb` (Notifications enabled)

### B. Cryptographic Specifications
* **Cipher**: AES-128 in ECB mode (`AES.MODE_ECB`).
* **Padding**: Standard PKCS#7 (16-byte blocks).
* **Checksum**: Modbus CRC-16 (Polynomial `0xA001`, Initial `0xFFFF`, Little-Endian byte order in protocol).
* **Hardcoded Factory Key**:
  ```python
  FACTORY_KEY = b"mQ3cJOATdERLW1a5"  # 16-byte ASCII
  ```
* **Pairing Credentials**:
  - `STATIC_MASTER_KEY`: 16-byte shared secret generated/exchanged during pairing.
  - `LOCK_SALT`: 4-byte salt (8-character hex, e.g. `1a2b3c4d`).

### C. Frame Construction & Decoding
* **Frame Header**: ASCII `HSJ` (`0x48 0x53 0x4A`).
* **Plaintext Frame Format**:
  `[HSJ Header (3B)] + [Cmd ID (2B)] + [Length (2B)] + [Payload (NB)] + [CRC16 (2B)]`
* **Encrypted Transmission**: Payload sections are encrypted using `STATIC_MASTER_KEY` (or `FACTORY_KEY` during unbonded pairing).

### D. Key Event Categories (Cmd ID `0x000A`)
* **Category `0x04`**: Unlocked Successfully
  - Credential Types: `0x01` Fingerprint, `0x02` PIN Code, `0x04` NFC Card, `0x00` App Remote.
  - Includes user ID slot and timestamp.
* **Category `0x36`**: Access Denied / Tamper Warning
  - Credential Types: Unregistered fingerprint, wrong keypad PIN, unauthorized NFC card.
  - Captures bad PIN ASCII strings entered on keypad.
* **Category `0x3D`**: Auto-Lock / Latch Engaged
  - Signals automatic bolt engagement after unlock window expires (default: 5 seconds).

### E. Pairing & Key Extraction Options
1. **Direct Native BLE Pairing (Zero-Snoop)**:
   Because `FACTORY_KEY` is known, `pyatomberg` can connect to a factory-reset lock, execute the initial pairing frame sequence, write a new random `STATIC_MASTER_KEY` and `LOCK_SALT`, and store them in Home Assistant config entries without Android Developer Options or ADB.
2. **BTSnoop Parser Fallback**:
   For locks already paired to the official Atomberg app, `pyatomberg.lock.pairing` provides an automated parser that scans `btsnoop_hci.log` (from `adb bugreport`), isolates GATT writes on `0xFFF1`, decrypts the handshake with `FACTORY_KEY`, and extracts `STATIC_MASTER_KEY` and `LOCK_SALT`.

---

## 5. Smart Locks Protocol: Gecko / Sitana Wi-Fi

Applies to **Atomberg SL1.0 / Azhero Series** smart mortise locks.

* **Architecture**: Combines onboard Wi-Fi (2.4 GHz) with Bluetooth Low Energy.
* **Chipset**: Silicon Labs Wireless Gecko (EFR32 SoC).
* **Wi-Fi Provisioning**: BLE strategy (`SitanaProvisionStrategy` / `SitanaChangeWifiUseCase`) passes home SSID and WPA2 passphrase to the lock.
* **Cloud Architecture**:
  - Primary Database: Google Firebase Firestore (`GeckoLock.fromFirestore`).
  - Event Flow: Visitor interaction creates a `sitana_unlock_request` document in Firestore.
  - Mobile App Hook: Fires push notification to `SitanaUnlockSheet`.
  - Cloud Decision: Owner approval dispatches command via `POST /update_device_state/sitanaunlock/decision` queued into `/update_device_state/lockcommands`.
* **Offline LRP Passwords**: For offline scenarios, the lock calculates dynamic OTPs based on shared counter/time algorithms (`/lrp/get_dynamic_password`).

---

## 6. Extended Device Models: Purifiers & Cooktops

Atomberg's unified cloud payload (`/app_open`) includes telemetry models for other household appliances:

### A. Smart Water Purifiers (W-Series / W4)
* **Model Identifiers**: `tanker40V2`, `w4_state_update`.
* **Available Telemetry**:
  - `input_tds` (PPM): Raw incoming water quality.
  - `output_tds` (PPM): Drinking water quality.
  - `filter_life` (%): Health percentages for Pre-Filter, Carbon Filter, RO Membrane, Post-Carbon Filter.
  - `tank_status`: `tank_empty`, `tank_filling`, `tank_full`.
  - `purification_mode`: `ro_mode`, `uv_mode`, `ro_cleaning`, `flushing`.
  - `water_consumed_liters` & `water_saved_liters`.

### B. Smart Induction Cooktops
* **Model Identifier**: `Cooktop.fromAppOpen`.
* **Available Controls & Telemetry**:
  - `power`: Binary on/off state.
  - `heat_level`: Wattage/temperature stages.
  - `timer`: Remaining cook countdown.
  - `child_lock`: Front-panel lockout toggle.

---

## 7. Hardware Provenance & Ecosystem Analysis

* **Lock Hardware (SL1 / SL1 Pro)**:
  - **OEM**: **Fujian Haosj Electronic Science & Technology Co., Ltd. (HSJiao)**, Fujian, China.
  - **Distinction**: Not TTLock (Sciener) and not Tuya. Uses Haosj’s proprietary fixed-key AES-128 protocol.
* **Lock Hardware (Wi-Fi Azhero)**:
  - **SoC**: Silicon Labs Wireless Gecko (EFR32).
* **Fan Hardware**:
  - **Motor**: In-house BLDC motor designed and manufactured by Atomberg in India.
  - **IoT Module**: Espressif ESP32 / Beken Wi-Fi microcontroller running custom "Phoenix" firmware with local UDP broadcasting.
* **Ecosystem Synergy vs. Qubo/TTLock**:
  - Atomberg's AWS Mumbai backend (`ap-south-1`) delivers lower latency for Indian users compared to TTLock's overseas servers.
  - Combining Atomberg fans and locks under `pyatomberg` provides a single unified library for Home Assistant instead of fragmented vendor plugins.

---

## 8. Target Library Architecture (`pyatomberg`)

```text
atomberg-py/
├── pyatomberg/
│   ├── __init__.py              # Package entry point
│   ├── const.py                 # Protocol UUIDs, factory keys, endpoints, UDP port 5625
│   ├── exceptions.py            # Authentication, BLE, and connection exception classes
│   ├── client.py                # AtombergClient (Cognito auth, /app_open device loader)
│   ├── crypto.py                # AES-128-ECB and Modbus CRC-16 routines
│   ├── fan/
│   │   ├── __init__.py
│   │   ├── device.py            # AtombergFan: speed (1-6), power, timer, LED, sleep
│   │   └── udp_listener.py      # Async UDP socket listener on port 5625
│   ├── lock/
│   │   ├── __init__.py
│   │   ├── device.py            # AtombergLock: Bleak BLE client
│   │   ├── hsj_protocol.py      # Haosj frame builder, parser, access log decoder
│   │   ├── pairing.py           # Native BLE pairing handshake tool & BTSnoop parser
│   │   └── models.py            # Lock events, credentials (NFC/PIN/fingerprint), battery
│   ├── purifier/
│   │   ├── __init__.py
│   │   └── device.py            # AtombergWaterPurifier: TDS, filter life, tank level
│   ├── cooktop/
│   │   ├── __init__.py
│   │   └── device.py            # AtombergCooktop: power, timer, temperature presets
│   ├── models/
│   │   ├── base.py
│   │   └── device.py            # Unified device dataclasses from fromAppOpen
│   └── cli.py                   # Command-line interface for testing and pairing
├── tests/
│   ├── test_crypto.py           # Validates AES-128 and Modbus CRC-16 against known test vectors
│   ├── test_hsj_protocol.py     # Validates frame creation and notification decoding
│   └── test_udp_listener.py     # Validates PROXY TCP4 datagram parsing
├── pyproject.toml               # Poetry/Build configuration (bleak, cryptography, aiohttp)
├── README.md                    # Installation, CLI documentation, and HA integration guide
└── HANDOVER.md                  # This document
```

---

## 9. Hardware Resumption Checklist & Action Plan

When the physical smart fans and door lock are delivered and installed:

### Phase 1: Environment & Repository Setup
- [ ] Initialize git repository in `D:\GitHub\atomberg-py`.
- [ ] Install dependencies in local virtualenv (`bleak`, `cryptography`, `aiohttp`, `pydantic`, `pytest`).

### Phase 2: Cryptography & Framing Verification
- [ ] Implement `pyatomberg/crypto.py` (AES-128-ECB and Modbus CRC-16).
- [ ] Run test suite with known test vectors from `dreadedlama/atomberg-lock` and APK dumps.

### Phase 3: Live Fan Integration (Cloud + Local UDP)
- [ ] Pair fans to home Wi-Fi via official Atomberg app.
- [ ] Activate Developer Mode in app settings to obtain developer `refresh_token` and `api_key`.
- [ ] Test `api.developer.atomberg-iot.com` REST client in `pyatomberg/fan/device.py`.
- [ ] Run `UDPListener` on port 5625 and verify incoming `PROXY TCP4` packets while toggling fan speeds.

### Phase 4: Live Lock Integration (BLE / Haosj)
- [ ] Place lock in BLE pairing mode or capture initial pairing handshake.
- [ ] Validate lock MAC, `STATIC_MASTER_KEY`, and `LOCK_SALT` generation.
- [ ] Verify local unlock command over BLE characteristic `0xFFF1`.
- [ ] Verify notification stream on `0xFFF2` (live battery status and audit log events).

### Phase 5: Home Assistant Custom Integration Packaging
- [ ] Scaffold `custom_components/atomberg` consuming `pyatomberg`.
- [ ] Implement `fan.py` with 6 speeds, sleep toggle, timer, and local UDP coordinator.
- [ ] Implement `lock.py` using Home Assistant's `bluetooth` component (`async_ble_device_from_address`).
- [ ] Add sensors for battery level, last unlock credential type, and last user.
