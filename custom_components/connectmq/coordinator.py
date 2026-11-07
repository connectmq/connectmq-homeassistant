"""Data update coordinator for ConnectMQ."""

from __future__ import annotations

from dataclasses import dataclass
import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import ConnectMQApi, ConnectMQAuthError, ConnectMQError
from .const import CONF_BROKER_ID, DOMAIN, SCAN_INTERVAL

_LOGGER = logging.getLogger(__name__)

type ConnectMQConfigEntry = ConfigEntry[ConnectMQCoordinator]


@dataclass
class ConnectMQData:
    """Snapshot of one broker and the account it belongs to."""

    broker: dict[str, Any]
    clients: list[dict[str, Any]]
    summary: dict[str, Any]
    quota: dict[str, Any]

    @property
    def online_clients(self) -> int:
        """Clients of this broker that are connected right now (portal sessions excluded)."""
        return sum(
            1
            for client in self.clients
            if client.get("state") == "online" and not client.get("isPortal")
        )


class ConnectMQCoordinator(DataUpdateCoordinator[ConnectMQData]):
    """Polls the ConnectMQ portal API."""

    config_entry: ConnectMQConfigEntry

    def __init__(
        self, hass: HomeAssistant, entry: ConnectMQConfigEntry, api: ConnectMQApi
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=SCAN_INTERVAL,
        )
        self.api = api
        self.broker_id: int = entry.data[CONF_BROKER_ID]

    async def _async_update_data(self) -> ConnectMQData:
        try:
            broker = await self.api.async_get_broker(self.broker_id)
            clients = await self.api.async_get_clients(self.broker_id)
            summary = await self.api.async_get_clients_summary()
            quota = await self.api.async_get_quota()
        except ConnectMQAuthError as err:
            raise ConfigEntryAuthFailed(
                translation_domain=DOMAIN, translation_key="session_expired"
            ) from err
        except ConnectMQError as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="update_failed",
                translation_placeholders={"error": str(err)},
            ) from err
        return ConnectMQData(broker=broker, clients=clients, summary=summary, quota=quota)
