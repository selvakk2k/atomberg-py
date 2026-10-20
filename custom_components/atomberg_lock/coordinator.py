"""DataUpdateCoordinator for Atomberg Smart Lock integration.

Based on protocol reverse engineering by dreadedlama (https://github.com/dreadedlama/atomberg-lock)
under GNU General Public License v3.0.
"""

from __future__ import annotations

import asyncio
from datetime import timedelta
import logging
from typing import Any

from homeassistant.components import bluetooth
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from pyatomberg.lock.device import AtombergLock
from pyatomberg.lock.hsj_protocol import LiveEvent

from .const import AUTO_LOCK_SECONDS, CONF_MAC, CONF_MASTER_KEY, CONF_SALT, CONF_SLOT_MAPPINGS, DOMAIN

_LOGGER = logging.getLogger(__name__)


class AtombergLockCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Coordinates BLE communication and state management for an Atomberg smart lock."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_{entry.data[CONF_MAC]}",
            update_interval=timedelta(minutes=30),  # Periodic battery & log sync
        )
        self.entry = entry
        self.address = str(entry.data[CONF_MAC]).upper()

        raw_key = entry.data[CONF_MASTER_KEY]
        if isinstance(raw_key, str):
            raw_key_str = raw_key.strip()
            if len(raw_key_str) == 32:
                try:
                    self.master_key = bytes.fromhex(raw_key_str)
                except ValueError:
                    self.master_key = raw_key_str.encode("utf-8")
            else:
                self.master_key = raw_key_str.encode("utf-8")
        else:
            self.master_key = bytes(raw_key)

        raw_salt = entry.data[CONF_SALT]
        if isinstance(raw_salt, str):
            self.lock_salt = bytes.fromhex(raw_salt.strip().replace(" ", "").replace("0x", ""))
        else:
            self.lock_salt = bytes(raw_salt)

        self.slot_mappings: dict[int, str] = dict(entry.options.get(CONF_SLOT_MAPPINGS, {}))

        # Runtime states
        self.is_locked = True
        self.is_unlocking = False
        self.battery_level: int | None = entry.data.get("battery_level")
        self.last_event: LiveEvent | None = None
        self.is_available = True

        self._lock_device: AtombergLock | None = None
        self._busy = asyncio.Lock()
        self._relock_task: asyncio.Task[None] | None = None
        self._log_store = Store[list[dict[str, Any]]](hass, 1, f"{DOMAIN}_{entry.entry_id}_logs")

    def _get_ble_device(self) -> Any:
        """Retrieve current BLEDevice from Home Assistant Bluetooth stack."""
        return bluetooth.async_ble_device_from_address(
            self.hass, self.address, connectable=True
        )

    def _ensure_lock_instance(self) -> AtombergLock:
        """Instantiate or update AtombergLock with latest BLE device reference."""
        ble_dev = self._get_ble_device()
        if self._lock_device is None:
            self._lock_device = AtombergLock(
                mac_address=self.address,
                master_key=self.master_key,
                salt=self.lock_salt,
                ble_device=ble_dev,
                slot_mappings=self.slot_mappings,
            )
            self._lock_device.register_event_callback(self._handle_live_event)
        else:
            self._lock_device.ble_device = ble_dev
            self._lock_device.slot_mappings = self.slot_mappings

        return self._lock_device

    def _handle_live_event(self, event: LiveEvent) -> None:
        """Handle real-time notification from lock hardware."""
        _LOGGER.debug("Received live lock event: %s (%s)", event.event, event.credential_type)
        self.last_event = event

        if event.is_unlocked:
            self.is_locked = False
            self._schedule_auto_relock()

        if event.is_auto_lock:
            self.is_locked = True

        if event.battery is not None and 0 <= event.battery <= 100:
            self.battery_level = event.battery

        self.async_set_updated_data(self._build_data_dict())

    def _schedule_auto_relock(self) -> None:
        """Schedule optimistic relock matching hardware latch timeout."""
        if self._relock_task and not self._relock_task.done():
            self._relock_task.cancel()

        async def _relock_coro() -> None:
            await asyncio.sleep(AUTO_LOCK_SECONDS)
            self.is_locked = True
            self.is_unlocking = False
            self.async_set_updated_data(self._build_data_dict())

        self._relock_task = self.hass.async_create_background_task(
            _relock_coro(), f"{DOMAIN}_auto_relock_{self.address}"
        )

    def _build_data_dict(self) -> dict[str, Any]:
        """Build summary data dictionary for listeners."""
        return {
            "is_locked": self.is_locked,
            "is_unlocking": self.is_unlocking,
            "battery_level": self.battery_level,
            "last_event": self.last_event.event if self.last_event else None,
            "credential_type": self.last_event.credential_type if self.last_event else None,
            "slot_id": self.last_event.slot_id if self.last_event else None,
            "pin_code": self.last_event.pin_code if self.last_event else None,
            "timestamp": self.last_event.timestamp if self.last_event else None,
        }

    async def _async_update_data(self) -> dict[str, Any]:
        """Poll lock status and battery periodically over BLE."""
        ble_dev = self._get_ble_device()
        if not ble_dev:
            self.is_available = False
            return self._build_data_dict()

        self.is_available = True
        lock = self._ensure_lock_instance()

        # Connect briefly to query battery
        async with self._busy:
            try:
                await lock.connect(timeout=10.0)
                await lock.authenticate()
                battery = await lock.get_battery()
                if battery is not None:
                    self.battery_level = battery
            except Exception as err:
                _LOGGER.debug("Could not poll lock battery: %s", err)
            finally:
                await lock.disconnect()

        return self._build_data_dict()

    async def async_unlock(self) -> None:
        """Dispatch unlock command over BLE."""
        ble_dev = self._get_ble_device()
        if not ble_dev:
            raise HomeAssistantError(f"Atomberg lock {self.address} is not in Bluetooth range")

        lock = self._ensure_lock_instance()
        self.is_unlocking = True
        self.async_set_updated_data(self._build_data_dict())

        async with self._busy:
            try:
                await lock.connect(timeout=10.0)
                await lock.authenticate()
                await lock.unlock()
                self.is_locked = False
                self.is_unlocking = False
                self._schedule_auto_relock()
                self.async_set_updated_data(self._build_data_dict())
            except Exception as err:
                self.is_unlocking = False
                self.async_set_updated_data(self._build_data_dict())
                raise HomeAssistantError(f"Failed to unlock Atomberg lock: {err}") from err
            finally:
                await lock.disconnect()
