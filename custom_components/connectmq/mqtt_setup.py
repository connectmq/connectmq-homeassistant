"""Set up Home Assistant's own MQTT integration with a ConnectMQ broker.

This does not replace the MQTT integration: it fills in the MQTT integration's own
config flow with the broker's host, TLS port, credentials and the client ID that
ConnectMQ expects, exactly as a user would type them. If that is not possible (for
example because MQTT is already configured), the values are shown in a notification
so they can be entered by hand.
"""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components import persistent_notification
from homeassistant.config_entries import SOURCE_USER
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .api import active_credential
from .const import DOMAIN, MQTT_CLIENT_ID_SUFFIX

_LOGGER = logging.getLogger(__name__)

MQTT_DOMAIN = "mqtt"


def mqtt_settings(broker: dict[str, Any]) -> dict[str, Any] | None:
    """Return the MQTT connection settings for a ConnectMQ broker."""
    credential = active_credential(broker)
    if credential is None:
        return None
    return {
        "broker": broker.get("hostName") or "broker.connectmq.com",
        "port": broker.get("mqttsPort") or 8883,
        "username": credential["username"],
        "password": credential["password"],
        "client_id": f"{credential['clientId']}{MQTT_CLIENT_ID_SUFFIX}",
    }


def mqtt_is_configured(hass: HomeAssistant) -> bool:
    """Return True when the MQTT integration already has a config entry."""
    return bool(hass.config_entries.async_entries(MQTT_DOMAIN))


async def async_configure_mqtt(hass: HomeAssistant, broker: dict[str, Any]) -> bool:
    """Create the MQTT integration entry for this broker. Returns True on success."""
    settings = mqtt_settings(broker)
    if settings is None or mqtt_is_configured(hass):
        return False

    flow_manager = hass.config_entries.flow
    flow_id: str | None = None
    try:
        result = await flow_manager.async_init(MQTT_DOMAIN, context={"source": SOURCE_USER})
        flow_id = result.get("flow_id")
        # On Home Assistant OS the MQTT flow first offers the Mosquitto add-on or a broker
        if result["type"] is FlowResultType.MENU:
            result = await flow_manager.async_configure(flow_id, {"next_step_id": "broker"})
        if result["type"] is not FlowResultType.FORM or result.get("step_id") != "broker":
            _LOGGER.debug("Unexpected MQTT flow step: %s", result)
            return False
        result = await flow_manager.async_configure(
            flow_id,
            {
                "broker": settings["broker"],
                "port": settings["port"],
                "protocol": "5",
                "username": settings["username"],
                "password": settings["password"],
                "other_settings": {
                    "client_id": settings["client_id"],
                    "keepalive": 60,
                    "set_client_cert": False,
                    "set_ca_cert": "auto",
                    "tls_insecure": False,
                    "transport": "tcp",
                },
            },
        )
    except Exception:  # noqa: BLE001 - the MQTT flow's schema is not a public API
        _LOGGER.warning(
            "Could not configure the MQTT integration automatically", exc_info=True
        )
        if flow_id:
            try:
                flow_manager.async_abort(flow_id)
            except Exception:  # noqa: BLE001
                pass
        return False

    if result["type"] is FlowResultType.CREATE_ENTRY:
        return True
    _LOGGER.warning("The MQTT integration did not accept the ConnectMQ settings: %s", result.get("errors"))
    if result["type"] is FlowResultType.FORM and flow_id:
        flow_manager.async_abort(flow_id)
    return False


def async_notify_manual_setup(hass: HomeAssistant, broker: dict[str, Any]) -> None:
    """Show the MQTT settings to enter by hand."""
    settings = mqtt_settings(broker)
    if settings is None:
        return
    message = (
        "Use these settings in **Settings → Devices & services → MQTT**"
        " (open *Advanced options* for the client ID and TLS):\n\n"
        f"- Broker: `{settings['broker']}`\n"
        f"- Port: `{settings['port']}`\n"
        f"- Username: `{settings['username']}`\n"
        "- Password: the password shown for this broker in the ConnectMQ portal\n"
        f"- Client ID: `{settings['client_id']}`\n"
        "- Broker certificate validation: **Auto**\n"
        "- Transport: **TCP**, MQTT protocol: **5**\n\n"
        "ConnectMQ only accepts the issued client ID or the issued ID followed by"
        " `_<suffix>`, so the client ID must be set exactly as above."
    )
    persistent_notification.async_create(
        hass,
        message,
        title=f"ConnectMQ: connect MQTT to {broker.get('name', 'your broker')}",
        notification_id=f"{DOMAIN}_mqtt_{broker.get('id')}",
    )
