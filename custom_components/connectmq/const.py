"""Constants for the ConnectMQ integration."""

from __future__ import annotations

from datetime import timedelta
from typing import Final

DOMAIN: Final = "connectmq"
MANUFACTURER: Final = "ConnectMQ"

API_BASE_URL: Final = "https://webapi.connectmq.com/api"
PORTAL_URL: Final = "https://app.connectmq.com"

CONF_REFRESH_TOKEN: Final = "refresh_token"
CONF_BROKER_ID: Final = "broker_id"
CONF_CONFIGURE_MQTT: Final = "configure_mqtt"

# ConnectMQ binds client IDs to the issued credentials: a client may use the issued
# client ID or the issued ID followed by "_<suffix>".
MQTT_CLIENT_ID_SUFFIX: Final = "_homeassistant"

SCAN_INTERVAL: Final = timedelta(minutes=5)

# A broker node is considered online when its last heartbeat is this recent.
NODE_HEARTBEAT_TIMEOUT: Final = timedelta(minutes=5)
