"""Atomberg mobile cloud sync client for importing registered smart locks."""

from __future__ import annotations

import logging
from typing import Any

import aiohttp

from pyatomberg.const import SERVER_API_BASE
from pyatomberg.exceptions import AtombergAuthError, AtombergConnectionError
from pyatomberg.lock.device import AtombergLock
from pyatomberg.lock.pairing import PairingResult

_LOGGER = logging.getLogger(__name__)


class AtombergCloudSync:
    """Fetches already-paired lock encryption keys and metadata from the Atomberg mobile backend."""

    def __init__(
        self,
        id_token: str,
        session: aiohttp.ClientSession | None = None,
        base_url: str = SERVER_API_BASE,
    ) -> None:
        """Initialize cloud sync client with Cognito ID token."""
        if not id_token:
            raise AtombergAuthError("Cognito ID token is required for cloud account sync")

        self._id_token = id_token
        self._session = session
        self._owns_session = session is None
        self._base_url = base_url.rstrip("/")

    async def fetch_account_locks(self) -> list[PairingResult]:
        """Fetch all smart locks registered to this Atomberg account with encryption parameters."""
        url = f"{self._base_url}/app_open"
        headers = {
            "Authorization": f"Bearer {self._id_token}",
            "Content-Type": "application/json",
        }

        session = self._session
        if session is None or session.closed:
            session = aiohttp.ClientSession()
            self._session = session

        try:
            async with session.post(url, json={}, headers=headers, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                if resp.status != 200:
                    raise AtombergConnectionError(f"Cloud server returned HTTP {resp.status}")

                data: dict[str, Any] = await resp.json(content_type=None)
                devices = (
                    data.get("devices")
                    or data.get("data", {}).get("devices")
                    or data.get("data", {}).get("locks")
                    or data.get("locks")
                    or []
                )

                results: list[PairingResult] = []
                for item in devices:
                    if not isinstance(item, dict):
                        continue

                    # Check for lock indicators
                    dev_type = item.get("device_type", item.get("type", "")).lower()
                    if "lock" not in dev_type and "sitana" not in dev_type and "hsj" not in dev_type:
                        continue

                    mac = item.get("mac_address") or item.get("mac") or item.get("device_id")
                    raw_key = item.get("master_key") or item.get("static_key") or item.get("key")
                    raw_salt = item.get("salt") or item.get("lock_salt")

                    if not mac or not raw_key or not raw_salt:
                        continue

                    # Parse key (can be hex string or ASCII)
                    if isinstance(raw_key, str):
                        raw_key_str = raw_key.strip()
                        if len(raw_key_str) == 32:
                            try:
                                key_bytes = bytes.fromhex(raw_key_str)
                            except ValueError:
                                key_bytes = raw_key_str.encode("utf-8")
                        else:
                            key_bytes = raw_key_str.encode("utf-8")
                    else:
                        key_bytes = bytes(raw_key)

                    # Parse salt (hex string)
                    if isinstance(raw_salt, str):
                        salt_clean = raw_salt.strip().replace(" ", "").replace("0x", "")
                        salt_bytes = bytes.fromhex(salt_clean)
                    else:
                        salt_bytes = bytes(raw_salt)

                    results.append(
                        PairingResult(
                            mac_address=str(mac).upper(),
                            master_key=key_bytes,
                            salt=salt_bytes,
                        )
                    )

                return results
        except aiohttp.ClientError as err:
            raise AtombergConnectionError(f"Network error querying app_open: {err}") from err
        finally:
            if self._owns_session and self._session and not self._session.closed:
                await self._session.close()
