"""Tracks person.* location changes and writes them to PostgreSQL."""
from __future__ import annotations

import logging
from collections import deque
from datetime import datetime, timezone
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
    outage can't grow memory unbounded.
    """

    def __init__(self, hass: HomeAssistant, store: PostgresStore) -> None:
        self._hass = hass
        self._store = store
        self._pending: deque[dict[str, Any]] = deque(maxlen=MAX_PENDING_POINTS)
        self._unsub_state = None
        self._unsub_retry = None

    def async_start(self) -> None:
        self._unsub_state = self._hass.bus.async_listen(
            "state_changed", self._handle_state_changed
        )
        self._unsub_retry = async_track_time_interval(
            self._hass, self._async_retry_pending, RETRY_INTERVAL_SECONDS
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

    async def _async_retry_pending(self, _now) -> None:
        if not self._pending:
            return
        remaining: deque[dict[str, Any]] = deque(maxlen=MAX_PENDING_POINTS)
        while self._pending:
            point = self._pending.popleft()
            try:
                await self._store.async_insert_point(point)
            except PostgresError:
                remaining.append(point)
        if remaining:
            _LOGGER.warning(
                "%d person location point(s) still pending after retry", len(remaining)
            )
            self._pending = remaining
