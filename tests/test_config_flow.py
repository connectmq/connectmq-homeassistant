"""Tests for the ConnectMQ config flow."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from custom_components.connectmq.const import API_BASE_URL, DOMAIN

BROKER = {
    "id": 42,
    "name": "Home",
    "status": "active",
    "planName": "Serverless (Free)",
    "brokerCode": "abc",
    "hostName": "broker.connectmq.com",
    "mqttPort": 1883,
    "mqttsPort": 8883,
    "wsPort": 8083,
    "wssPort": 8084,
    "wsPath": "/mqtt",
    "nodeRegistered": False,
    "credentials": [
        {"id": 1, "username": "u1", "password": "p1", "clientId": "cid1", "isActive": True}
    ],
}
TOKENS = {
    "accessToken": "at",
    "accessTokenExpiresAt": "2099-01-01T00:00:00Z",
    "refreshToken": "rt1",
    "refreshTokenExpiresAt": "2099-01-01T00:00:00Z",
    "me": {"user": {"id": 7, "email": "a@b.c"}},
}


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Enable custom integrations."""
    return


def _mock_api(aioclient_mock):
    aioclient_mock.post(f"{API_BASE_URL}/auth/login", json=TOKENS)
    aioclient_mock.post(f"{API_BASE_URL}/auth/refresh", json={**TOKENS, "refreshToken": "rt2"})
    aioclient_mock.get(f"{API_BASE_URL}/brokers", json=[BROKER])
    aioclient_mock.get(f"{API_BASE_URL}/brokers/42", json=BROKER)
    aioclient_mock.get(f"{API_BASE_URL}/clients", json=[])
    aioclient_mock.get(
        f"{API_BASE_URL}/clients/summary",
        json={"online": 1, "total": 3, "maxConcurrentConnections": 25, "remainingConnections": 24},
    )
    aioclient_mock.get(
        f"{API_BASE_URL}/me/quota",
        json={"sessionMinutesUsed": 10, "sessionMinutesLimit": 1000, "usedPercent": 1.0},
    )


async def test_invalid_auth(hass: HomeAssistant, aioclient_mock) -> None:
    """Wrong password shows an error."""
    aioclient_mock.post(
        f"{API_BASE_URL}/auth/login", status=401, json={"code": "InvalidCredentials"}
    )
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"email": "a@b.c", "password": "x"}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_auth"}


async def test_flow_without_mqtt(hass: HomeAssistant, aioclient_mock) -> None:
    """Sign in, single broker is picked automatically, MQTT setup declined."""
    _mock_api(aioclient_mock)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"email": "a@b.c", "password": "pw"}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "mqtt"
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"configure_mqtt": False}
    )
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Home"
    assert result["data"]["refresh_token"] == "rt1"
    assert result["data"]["broker_id"] == 42

    state = hass.states.get("sensor.home_connected_clients")
    assert state is not None and state.state == "0"
    assert hass.states.get("sensor.home_remaining_connections").state == "24"
    assert hass.states.get("binary_sensor.home_broker_active").state == "on"
    assert hass.states.get("binary_sensor.home_broker_node") is None
    # The rotated refresh token is persisted right away
    entry = hass.config_entries.async_entries(DOMAIN)[0]
    assert entry.data["refresh_token"] == "rt2"


async def test_flow_configures_mqtt(hass: HomeAssistant, aioclient_mock) -> None:
    """The MQTT integration entry is created with the ConnectMQ settings."""
    _mock_api(aioclient_mock)
    with patch(
        "homeassistant.components.mqtt.config_flow.try_connection", return_value=True
    ), patch("homeassistant.components.mqtt.async_setup_entry", return_value=True):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"email": "a@b.c", "password": "pw"}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"configure_mqtt": True}
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    mqtt_entries = hass.config_entries.async_entries("mqtt")
    assert len(mqtt_entries) == 1, "MQTT entry was not created"
    data = mqtt_entries[0].data
    print("MQTT entry data:", {k: v for k, v in data.items() if k != "password"})
    assert data["broker"] == "broker.connectmq.com"
    assert data["port"] == 8883
    assert data["username"] == "u1"
    assert data["password"] == "p1"
    assert data["client_id"] == "cid1_homeassistant"
