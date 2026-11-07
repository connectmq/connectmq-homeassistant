"""Async client for the ConnectMQ portal API."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta
import logging
from typing import Any

import aiohttp

from .const import API_BASE_URL

_LOGGER = logging.getLogger(__name__)

REQUEST_TIMEOUT = aiohttp.ClientTimeout(total=30)


class ConnectMQError(Exception):
    """Raised when the ConnectMQ API cannot be reached or returns an error."""


class ConnectMQAuthError(ConnectMQError):
    """Raised when the credentials or the session are no longer valid."""


def parse_time(value: str | None) -> datetime | None:
    """Parse an ISO 8601 timestamp returned by the API."""
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


async def _post_json(
    session: aiohttp.ClientSession, path: str, body: dict[str, Any]
) -> dict[str, Any]:
    try:
        async with session.post(
            f"{API_BASE_URL}{path}", json=body, timeout=REQUEST_TIMEOUT
        ) as resp:
            try:
                data = await resp.json(content_type=None)
            except ValueError:
                data = None
            if not isinstance(data, dict):
                data = {}
            if resp.status in (400, 401, 403):
                raise ConnectMQAuthError((data or {}).get("code", f"HTTP {resp.status}"))
            if resp.status >= 400:
                raise ConnectMQError((data or {}).get("message", f"HTTP {resp.status}"))
            return data
    except (aiohttp.ClientError, TimeoutError) as err:
        raise ConnectMQError(str(err)) from err


async def async_login(
    session: aiohttp.ClientSession, email: str, password: str
) -> dict[str, Any]:
    """Sign in with e-mail and password and return the token response."""
    return await _post_json(session, "/auth/login", {"email": email, "password": password})


class ConnectMQApi:
    """Portal API client that keeps the access token fresh.

    The portal rotates refresh tokens: every refresh returns a new refresh token and
    revokes the old one. Reusing a revoked token signs the user out everywhere, so the
    new token is handed to ``on_refresh_token`` right away to be persisted.
    """

    def __init__(
        self,
        session: aiohttp.ClientSession,
        refresh_token: str,
        on_refresh_token: Callable[[str], Awaitable[None] | None] | None = None,
        access_token: str | None = None,
        access_token_expires: datetime | None = None,
    ) -> None:
        self._session = session
        self._refresh_token = refresh_token
        self._on_refresh_token = on_refresh_token
        self._access_token = access_token
        self._access_expires = access_token_expires
        self._lock = asyncio.Lock()

    @property
    def refresh_token(self) -> str:
        """The current refresh token."""
        return self._refresh_token

    def _token_valid(self) -> bool:
        return bool(
            self._access_token
            and self._access_expires
            and self._access_expires - timedelta(minutes=2) > datetime.now(UTC)
        )

    async def _async_refresh(self) -> None:
        async with self._lock:
            if self._token_valid():
                return
            data = await _post_json(
                self._session, "/auth/refresh", {"refreshToken": self._refresh_token}
            )
            self._access_token = data["accessToken"]
            self._access_expires = parse_time(data.get("accessTokenExpiresAt"))
            new_refresh = data.get("refreshToken")
            if new_refresh and new_refresh != self._refresh_token:
                self._refresh_token = new_refresh
                if self._on_refresh_token:
                    result = self._on_refresh_token(new_refresh)
                    if asyncio.iscoroutine(result):
                        await result

    async def _async_get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        if not self._token_valid():
            await self._async_refresh()
        for attempt in range(2):
            try:
                async with self._session.get(
                    f"{API_BASE_URL}{path}",
                    params=params,
                    headers={"Authorization": f"Bearer {self._access_token}"},
                    timeout=REQUEST_TIMEOUT,
                ) as resp:
                    if resp.status == 401 and attempt == 0:
                        self._access_token = None
                        await self._async_refresh()
                        continue
                    if resp.status in (401, 403):
                        raise ConnectMQAuthError(f"HTTP {resp.status}")
                    if resp.status >= 400:
                        raise ConnectMQError(f"{path}: HTTP {resp.status}")
                    return await resp.json(content_type=None)
            except (aiohttp.ClientError, TimeoutError) as err:
                raise ConnectMQError(str(err)) from err
        raise ConnectMQAuthError("unauthorized")

    async def async_get_me(self) -> dict[str, Any]:
        """Return the signed-in user, tenant and subscription."""
        return await self._async_get("/me")

    async def async_get_brokers(self) -> list[dict[str, Any]]:
        """Return the tenant's brokers with their MQTT credentials."""
        return await self._async_get("/brokers")

    async def async_get_broker(self, broker_id: int) -> dict[str, Any]:
        """Return one broker with its MQTT credentials."""
        return await self._async_get(f"/brokers/{broker_id}")

    async def async_get_clients(self, broker_id: int) -> list[dict[str, Any]]:
        """Return the clients (connections) of one broker."""
        return await self._async_get("/clients", {"tenantBrokerId": broker_id})

    async def async_get_clients_summary(self) -> dict[str, Any]:
        """Return open connections against the plan's connection limit."""
        return await self._async_get("/clients/summary")

    async def async_get_quota(self) -> dict[str, Any]:
        """Return the session-minute quota of the current period."""
        return await self._async_get("/me/quota")


def node_last_heartbeat(broker: dict[str, Any]) -> datetime | None:
    """Return the broker node's last heartbeat as an aware datetime."""
    return parse_time(broker.get("nodeLastHeartbeat"))


def active_credential(broker: dict[str, Any]) -> dict[str, Any] | None:
    """Return the first active MQTT credential of a broker."""
    for credential in broker.get("credentials") or []:
        if credential.get("isActive", True):
            return credential
    return None
