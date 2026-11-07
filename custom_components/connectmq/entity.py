"""Base entity for ConnectMQ."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MANUFACTURER, PORTAL_URL
from .coordinator import ConnectMQCoordinator


class ConnectMQEntity(CoordinatorEntity[ConnectMQCoordinator]):
    """An entity that belongs to one ConnectMQ broker (a service device)."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: ConnectMQCoordinator, key: str) -> None:
        super().__init__(coordinator)
        broker = coordinator.data.broker
        self._attr_unique_id = f"{coordinator.broker_id}_{key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, str(coordinator.broker_id))},
            name=broker.get("name") or broker.get("brokerCode") or "ConnectMQ broker",
            manufacturer=MANUFACTURER,
            model=broker.get("planName") or "MQTT broker",
            entry_type=DeviceEntryType.SERVICE,
            configuration_url=PORTAL_URL,
        )
