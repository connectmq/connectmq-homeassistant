"""The ConnectMQ integration: account status and easy MQTT setup for ConnectMQ brokers."""

from __future__ import annotations

import logging

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import ConnectMQApi
from .const import API_BASE_URL, CONF_REFRESH_TOKEN
from .coordinator import ConnectMQConfigEntry, ConnectMQCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.BINARY_SENSOR, Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConnectMQConfigEntry) -> bool:
    """Set up ConnectMQ from a config entry."""

    @callback
    def _store_refresh_token(token: str) -> None:
        # The portal rotates refresh tokens; persist the new one immediately
        hass.config_entries.async_update_entry(
            entry, data={**entry.data, CONF_REFRESH_TOKEN: token}
        )

    api = ConnectMQApi(
        async_get_clientsession(hass),
        entry.data[CONF_REFRESH_TOKEN],
        _store_refresh_token,
    )
    coordinator = ConnectMQCoordinator(hass, entry, api)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConnectMQConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_remove_entry(hass: HomeAssistant, entry: ConnectMQConfigEntry) -> None:
    """Sign the integration's session out of the portal when the entry is removed."""
    session = async_get_clientsession(hass)
    try:
        async with session.post(
            f"{API_BASE_URL}/auth/logout",
            json={"refreshToken": entry.data.get(CONF_REFRESH_TOKEN, "")},
        ):
            pass
    except Exception:  # noqa: BLE001 - best effort
        _LOGGER.debug("Could not sign out of ConnectMQ", exc_info=True)
