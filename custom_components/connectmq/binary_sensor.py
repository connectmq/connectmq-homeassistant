"""Binary sensors for ConnectMQ brokers."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .api import node_last_heartbeat
from .const import NODE_HEARTBEAT_TIMEOUT
from .coordinator import ConnectMQConfigEntry, ConnectMQData
from .entity import ConnectMQEntity

PARALLEL_UPDATES = 0


def _node_online(data: ConnectMQData) -> bool | None:
    if not data.broker.get("nodeRegistered"):
        return None  # shared (serverless) brokers have no node of their own
    heartbeat = node_last_heartbeat(data.broker)
    return heartbeat is not None and datetime.now(UTC) - heartbeat < NODE_HEARTBEAT_TIMEOUT


@dataclass(frozen=True, kw_only=True)
class ConnectMQBinarySensorDescription(BinarySensorEntityDescription):
    """Describes a ConnectMQ binary sensor."""

    value_fn: Callable[[ConnectMQData], bool | None]
    exists_fn: Callable[[ConnectMQData], bool] = lambda _: True


BINARY_SENSORS: tuple[ConnectMQBinarySensorDescription, ...] = (
    ConnectMQBinarySensorDescription(
        key="broker_active",
        translation_key="broker_active",
        device_class=BinarySensorDeviceClass.RUNNING,
        value_fn=lambda d: d.broker.get("status") == "active",
    ),
    ConnectMQBinarySensorDescription(
        key="node_online",
        translation_key="node_online",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        value_fn=_node_online,
        exists_fn=lambda d: bool(d.broker.get("nodeRegistered")),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConnectMQConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up ConnectMQ binary sensors."""
    coordinator = entry.runtime_data
    async_add_entities(
        ConnectMQBinarySensor(coordinator, description)
        for description in BINARY_SENSORS
        if description.exists_fn(coordinator.data)
    )


class ConnectMQBinarySensor(ConnectMQEntity, BinarySensorEntity):
    """A ConnectMQ binary sensor."""

    entity_description: ConnectMQBinarySensorDescription

    def __init__(self, coordinator, description: ConnectMQBinarySensorDescription) -> None:
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    def is_on(self) -> bool | None:
        """Return the state."""
        return self.entity_description.value_fn(self.coordinator.data)
