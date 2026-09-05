"""Tracks person.* location changes and writes them to PostgreSQL."""
from __future__ import annotations

import logging
from collections import deque
from collections.abc import Callable
from datetime import datetime, timedelta, timezone
from typing import Any

from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers.event import async_track_time_interval

from .const import MAX_PENDING_POINTS, RETRY_INTERVAL_SECONDS, TRACKED_DOMAIN
from .pg import PostgresError, PostgresStore

_LOGGER = logging.getLogger(__name__)


class PersonLocationCoordinator:
    """Listens for person state changes and persists them to Postgres.

    Failed inserts (e.g. the other VM briefly unreachable) are buffered in
    memory and retried on a timer, capped at MAX_PENDING_POINTS so a longer
    outage can't grow memory unbounded. Also tracks last success/error so a
    status sensor can show whether the integration is actually working.
    """

    def __init__(self, hass: HomeAssistant, store: PostgresStore) -> None:
        self._hass = hass
        self._store = store
        self._pending: deque[dict[str, Any]] = deque(maxlen=MAX_PENDING_POINTS)
        self._unsub_state = None
        self._unsub_retry = None
        self._listeners: list[Callable[[], None]] = []

        self.last_success: datetime | None = None
        self.last_error: str | None = None
        self.last_error_time: datetime | None = None

    @property
    def pending_count(self) -> int:
        return len(self._pending)

    @callback
    def async_add_listener(self, update_callback: Callable[[], None]) -> Callable[[], None]:
        """Register a callback invoked whenever the status changes."""
        self._listeners.append(update_callback)

        @callback
        def remove_listener() -> None:
            self._listeners.remove(update_callback)

        return remove_listener

    @callback
    def _notify_listeners(self) -> None:
        for update_callback in self._listeners:
            update_callback()

    @callback
    def mark_connected(self) -> None:
        """Record that the initial connection to PostgreSQL succeeded."""
        self.last_success = datetime.now(timezone.utc)
        self._notify_listeners()

    def async_start(self) -> None:
        self._unsub_state = self._hass.bus.async_listen(
            "state_changed", self._handle_state_changed
        )
        self._unsub_retry = async_track_time_interval(
            self._hass,
            self._async_retry_pending,
            timedelta(seconds=RETRY_INTERVAL_SECONDS),
        )

    def async_stop(self) -> None:
        if self._unsub_state:
            self._unsub_state()
            self._unsub_state = None
        if self._unsub_retry:
            self._unsub_retry()
            self._unsub_retry = None

    @callback
    def _handle_state_changed(self, event: Event) -> None:
        entity_id = event.data.get("entity_id", "")
        if not entity_id.startswith(f"{TRACKED_DOMAIN}."):
            return
        new_state = event.data.get("new_state")
        if new_state is None:
            return
        latitude = new_state.attributes.get("latitude")
        longitude = new_state.attributes.get("longitude")
        if latitude is None or longitude is None:
            return

        point = {
            "entity_id": entity_id,
            "name": new_state.attributes.get("friendly_name", entity_id),
            "state": new_state.state,
            "latitude": latitude,
            "longitude": longitude,
            "gps_accuracy": new_state.attributes.get("gps_accuracy"),
            "source": new_state.attributes.get("source"),
            "timestamp": datetime.now(timezone.utc),
        }
        self._hass.async_create_task(self._async_write(point))

    async def _async_write(self, point: dict[str, Any]) -> None:
        try:
            await self._store.async_insert_point(point)
        except PostgresError as err:
            _LOGGER.warning(
                "Could not write person location to PostgreSQL, will retry: %s", err
            )
            self._pending.append(point)
            self.last_error = str(err)
            self.last_error_time = datetime.now(timezone.utc)
        else:
            self.last_success = datetime.now(timezone.utc)
        self._notify_listeners()

    async def _async_retry_pending(self, _now) -> None:
        if not self._pending:
            return
        remaining: deque[dict[str, Any]] = deque(maxlen=MAX_PENDING_POINTS)
        while self._pending:
            point = self._pending.popleft()
            try:
                await self._store.async_insert_point(point)
            except PostgresError as err:
                remaining.append(point)
                self.last_error = str(err)
                self.last_error_time = datetime.now(timezone.utc)
            else:
                self.last_success = datetime.now(timezone.utc)
        if remaining:
            _LOGGER.warning(
                "%d person location point(s) still pending after retry", len(remaining)
            )
            self._pending = remaining
        self._notify_listeners()
