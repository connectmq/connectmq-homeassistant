"""Sensors for ConnectMQ brokers and account usage."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import PERCENTAGE, EntityCategory, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .api import parse_time
from .coordinator import ConnectMQConfigEntry, ConnectMQData
from .entity import ConnectMQEntity

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class ConnectMQSensorDescription(SensorEntityDescription):
    """Describes a ConnectMQ sensor."""

    value_fn: Callable[[ConnectMQData], Any]


SENSORS: tuple[ConnectMQSensorDescription, ...] = (
    ConnectMQSensorDescription(
        key="online_clients",
        translation_key="online_clients",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: d.online_clients,
    ),
    ConnectMQSensorDescription(
        key="account_connections",
        translation_key="account_connections",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: d.summary.get("online"),
    ),
    ConnectMQSensorDescription(
        key="connection_limit",
        translation_key="connection_limit",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda d: d.summary.get("maxConcurrentConnections"),
    ),
    ConnectMQSensorDescription(
        key="remaining_connections",
        translation_key="remaining_connections",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: d.summary.get("remainingConnections"),
    ),
    ConnectMQSensorDescription(
        key="session_minutes_used",
        translation_key="session_minutes_used",
        native_unit_of_measurement=UnitOfTime.MINUTES,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda d: d.quota.get("sessionMinutesUsed"),
    ),
    ConnectMQSensorDescription(
        key="session_minutes_limit",
        translation_key="session_minutes_limit",
        native_unit_of_measurement=UnitOfTime.MINUTES,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda d: d.quota.get("sessionMinutesLimit"),
    ),
    ConnectMQSensorDescription(
        key="quota_used",
        translation_key="quota_used",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=lambda d: d.quota.get("usedPercent"),
    ),
    ConnectMQSensorDescription(
        key="plan",
        translation_key="plan",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda d: d.broker.get("planName"),
    ),
    ConnectMQSensorDescription(
        key="last_client_connected",
        translation_key="last_client_connected",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=lambda d: parse_time(d.quota.get("lastConnectedAt")),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConnectMQConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up ConnectMQ sensors."""
    coordinator = entry.runtime_data
    async_add_entities(ConnectMQSensor(coordinator, description) for description in SENSORS)


class ConnectMQSensor(ConnectMQEntity, SensorEntity):
    """A ConnectMQ sensor."""

    entity_description: ConnectMQSensorDescription

    def __init__(self, coordinator, description: ConnectMQSensorDescription) -> None:
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    def native_value(self) -> str | int | float | datetime | None:
        """Return the sensor value."""
        return self.entity_description.value_fn(self.coordinator.data)
