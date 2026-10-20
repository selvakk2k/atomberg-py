"""Config flow and options flow for Atomberg Smart Lock integration."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant import config_entries
from homeassistant.components import bluetooth
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
import voluptuous as vol

from pyatomberg.lock.cloud_sync import AtombergCloudSync
from pyatomberg.lock.pairing import AtombergBLEPairingManager

from .const import (
    CONF_MAC,
    CONF_MASTER_KEY,
    CONF_PAIRING_METHOD,
    CONF_SALT,
    CONF_SLOT_MAPPINGS,
    DEFAULT_NAME,
    DOMAIN,
    METHOD_CLOUD,
    METHOD_MANUAL,
    METHOD_NATIVE,
)

_LOGGER = logging.getLogger(__name__)


class AtombergLockConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Atomberg Smart Lock."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the flow."""
        self._discovered_macs: dict[str, str] = {}
        self._selected_mac: str | None = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Choose between Native Pairing, Cloud Sync, or Manual Key Entry."""
        return self.async_show_menu(
            step_id="user",
            menu_options=[METHOD_NATIVE, METHOD_CLOUD, METHOD_MANUAL],
        )

    async def async_step_native(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Native Zero-Snoop Bluetooth pairing."""
        errors: dict[str, str] = {}

        # Scan for nearby Bluetooth devices
        current_macs = self._async_current_ids()
        for service_info in bluetooth.async_discovered_service_info(self.hass, connectable=True):
            mac = service_info.address.upper()
            if mac not in current_macs:
                name = service_info.name or f"Unknown Lock ({mac})"
                self._discovered_macs[mac] = f"{name} [{mac}]"

        if user_input is not None:
            mac = user_input[CONF_MAC]
            await self.async_set_unique_id(mac.upper())
            self._abort_if_unique_id_configured()

            # Execute native pairing handshake
            pairing_manager = AtombergBLEPairingManager()
            try:
                ble_device = bluetooth.async_ble_device_from_address(self.hass, mac, connectable=True)
                if not ble_device:
                    raise ValueError("Device not found by Bluetooth scanner")

                result = await pairing_manager.pair_device(ble_device)
                return self.async_create_entry(
                    title=f"Atomberg Lock ({mac})",
                    data={
                        CONF_MAC: result.mac_address,
                        CONF_MASTER_KEY: result.master_key_hex,
                        CONF_SALT: result.salt_hex,
                        CONF_PAIRING_METHOD: METHOD_NATIVE,
                    },
                )
            except Exception as err:
                _LOGGER.exception("Native pairing failed: %s", err)
                errors["base"] = "pairing_failed"

        schema = vol.Schema({
            vol.Required(CONF_MAC): vol.In(self._discovered_macs)
            if self._discovered_macs
            else str
        })
        return self.async_show_form(step_id="native", data_schema=schema, errors=errors)

    async def async_step_cloud(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Import lock credentials from Atomberg cloud account."""
        errors: dict[str, str] = {}

        if user_input is not None:
            id_token = user_input.get("id_token", "").strip()
            sync_client = AtombergCloudSync(id_token=id_token)

            try:
                locks = await sync_client.fetch_account_locks()
                if not locks:
                    errors["base"] = "no_locks_found"
                else:
                    first_lock = locks[0]
                    await self.async_set_unique_id(first_lock.mac_address)
                    self._abort_if_unique_id_configured()

                    return self.async_create_entry(
                        title=f"Atomberg Lock ({first_lock.mac_address})",
                        data={
                            CONF_MAC: first_lock.mac_address,
                            CONF_MASTER_KEY: first_lock.master_key_hex,
                            CONF_SALT: first_lock.salt_hex,
                            CONF_PAIRING_METHOD: METHOD_CLOUD,
                        },
                    )
            except Exception as err:
                _LOGGER.exception("Cloud sync failed: %s", err)
                errors["base"] = "cloud_sync_failed"

        schema = vol.Schema({
            vol.Required("id_token"): str,
        })
        return self.async_show_form(step_id="cloud", data_schema=schema, errors=errors)

    async def async_step_manual(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manual key entry for existing users or btsnoop log migrators."""
        errors: dict[str, str] = {}

        if user_input is not None:
            mac = user_input[CONF_MAC].strip().upper()
            await self.async_set_unique_id(mac)
            self._abort_if_unique_id_configured()

            return self.async_create_entry(
                title=f"Atomberg Lock ({mac})",
                data={
                    CONF_MAC: mac,
                    CONF_MASTER_KEY: user_input[CONF_MASTER_KEY].strip(),
                    CONF_SALT: user_input[CONF_SALT].strip(),
                    CONF_PAIRING_METHOD: METHOD_MANUAL,
                },
            )

        schema = vol.Schema({
            vol.Required(CONF_MAC): str,
            vol.Required(CONF_MASTER_KEY): str,
            vol.Required(CONF_SALT): str,
        })
        return self.async_show_form(step_id="manual", data_schema=schema, errors=errors)

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        """Return the options flow handler."""
        return AtombergLockOptionsFlow(config_entry)


class AtombergLockOptionsFlow(config_entries.OptionsFlow):
    """Handle options for Atomberg Lock (e.g. user/slot mappings)."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        self.config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage user slot mappings."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        current_mappings = self.config_entry.options.get(CONF_SLOT_MAPPINGS, {})
        schema = vol.Schema({
            vol.Optional(
                CONF_SLOT_MAPPINGS,
                default=current_mappings,
            ): dict,
        })
        return self.async_show_form(step_id="init", data_schema=schema)
