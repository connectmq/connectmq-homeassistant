"""Config flow for ConnectMQ."""

from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    BooleanSelector,
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .api import (
    ConnectMQApi,
    ConnectMQAuthError,
    ConnectMQError,
    active_credential,
    async_login,
    parse_time,
)
from .const import (
    CONF_BROKER_ID,
    CONF_CONFIGURE_MQTT,
    CONF_REFRESH_TOKEN,
    DOMAIN,
    PORTAL_URL,
)
from .mqtt_setup import async_configure_mqtt, async_notify_manual_setup, mqtt_is_configured

_LOGGER = logging.getLogger(__name__)

LOGIN_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_EMAIL): TextSelector(
            TextSelectorConfig(type=TextSelectorType.EMAIL, autocomplete="username")
        ),
        vol.Required(CONF_PASSWORD): TextSelector(
            TextSelectorConfig(type=TextSelectorType.PASSWORD, autocomplete="current-password")
        ),
    }
)


class ConnectMQConfigFlow(ConfigFlow, domain=DOMAIN):
    """Sign in to ConnectMQ, pick a broker and optionally set up MQTT."""

    VERSION = 1

    def __init__(self) -> None:
        self._email: str | None = None
        self._refresh_token: str | None = None
        self._api: ConnectMQApi | None = None
        self._brokers: dict[int, dict[str, Any]] = {}
        self._broker_id: int | None = None

    def _on_refresh_token(self, token: str) -> None:
        self._refresh_token = token

    async def _async_sign_in(self, email: str, password: str) -> dict[str, str]:
        """Sign in and keep the session for the next steps. Returns form errors."""
        session = async_get_clientsession(self.hass)
        try:
            tokens = await async_login(session, email, password)
        except ConnectMQAuthError:
            return {"base": "invalid_auth"}
        except ConnectMQError:
            return {"base": "cannot_connect"}
        self._email = email
        self._refresh_token = tokens["refreshToken"]
        self._api = ConnectMQApi(
            session,
            tokens["refreshToken"],
            self._on_refresh_token,
            access_token=tokens.get("accessToken"),
            access_token_expires=parse_time(tokens.get("accessTokenExpiresAt")),
        )
        return {}

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask for the ConnectMQ account."""
        errors: dict[str, str] = {}
        if user_input is not None:
            errors = await self._async_sign_in(
                user_input[CONF_EMAIL].strip(), user_input[CONF_PASSWORD]
            )
            if not errors:
                return await self.async_step_broker()
        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(LOGIN_SCHEMA, user_input),
            errors=errors,
            description_placeholders={"portal_url": PORTAL_URL},
        )

    async def async_step_broker(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Pick one of the account's brokers."""
        assert self._api is not None
        if not self._brokers:
            try:
                brokers = await self._api.async_get_brokers()
            except ConnectMQError:
                return self.async_abort(reason="cannot_connect")
            configured = {
                entry.data.get(CONF_BROKER_ID) for entry in self._async_current_entries()
            }
            self._brokers = {
                b["id"]: b
                for b in brokers
                if b.get("id") not in configured and active_credential(b) is not None
            }
            if not self._brokers:
                return self.async_abort(
                    reason="no_brokers", description_placeholders={"portal_url": PORTAL_URL}
                )

        if user_input is not None or len(self._brokers) == 1:
            broker_id = (
                int(user_input[CONF_BROKER_ID]) if user_input else next(iter(self._brokers))
            )
            await self.async_set_unique_id(f"broker_{broker_id}")
            self._abort_if_unique_id_configured()
            self._broker_id = broker_id
            return await self.async_step_mqtt()

        options = [
            SelectOptionDict(
                value=str(broker_id),
                label=f"{b.get('name') or b.get('brokerCode')} ({b.get('planName', '')})",
            )
            for broker_id, b in self._brokers.items()
        ]
        return self.async_show_form(
            step_id="broker",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_BROKER_ID): SelectSelector(
                        SelectSelectorConfig(options=options, mode=SelectSelectorMode.LIST)
                    )
                }
            ),
        )

    async def async_step_mqtt(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Offer to connect Home Assistant's MQTT integration to the broker."""
        assert self._broker_id is not None
        broker = self._brokers[self._broker_id]
        already = mqtt_is_configured(self.hass)

        if user_input is not None or already:
            if user_input and user_input.get(CONF_CONFIGURE_MQTT) and not already:
                if not await async_configure_mqtt(self.hass, broker):
                    async_notify_manual_setup(self.hass, broker)
            elif already:
                # Leave the user's existing MQTT setup alone, but show the settings
                async_notify_manual_setup(self.hass, broker)
            return self.async_create_entry(
                title=broker.get("name") or broker.get("brokerCode") or "ConnectMQ",
                data={
                    "email": self._email,
                    CONF_REFRESH_TOKEN: self._refresh_token,
                    CONF_BROKER_ID: self._broker_id,
                },
            )

        return self.async_show_form(
            step_id="mqtt",
            data_schema=vol.Schema(
                {vol.Required(CONF_CONFIGURE_MQTT, default=True): BooleanSelector()}
            ),
            description_placeholders={
                "broker": broker.get("name") or "",
                "host": broker.get("hostName") or "broker.connectmq.com",
                "port": str(broker.get("mqttsPort") or 8883),
            },
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Handle an expired session."""
        self._email = entry_data.get("email")
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask for the password again."""
        errors: dict[str, str] = {}
        if user_input is not None:
            email = user_input[CONF_EMAIL].strip()
            errors = await self._async_sign_in(email, user_input[CONF_PASSWORD])
            if not errors:
                return self.async_update_reload_and_abort(
                    self._get_reauth_entry(),
                    data_updates={"email": email, CONF_REFRESH_TOKEN: self._refresh_token},
                )
        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=self.add_suggested_values_to_schema(
                LOGIN_SCHEMA, {CONF_EMAIL: self._email}
            ),
            errors=errors,
        )
