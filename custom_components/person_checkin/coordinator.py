"""Tracks person.* location changes and persists them locally."""
from __future__ import annotations

import logging
from collections import deque
from datetime import datetime, timezone
from typing import Any

from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers.storage import Store

from .const import MAX_HISTORY_POINTS, STORAGE_KEY, STORAGE_VERSION, TRACKED_DOMAIN

_LOGGER = logging.getLogger(__name__)


class PersonLocationStore:
    """In-memory ring buffer of location points, debounced to disk."""

    def __init__(self, hass: HomeAssistant) -> None:
        self._hass = hass
        self._store: Store = Store(hass, STORAGE_VERSION, STORAGE_KEY)
        self._points: deque[dict[str, Any]] = deque(maxlen=MAX_HISTORY_POINTS)
        self._unsub_state = None

    async def async_load(self) -> None:
        data = await self._store.async_load()
        if data:
            self._points.extend(data.get("points", []))

    def async_start(self) -> None:
        self._unsub_state = self._hass.bus.async_listen(
            "state_changed", self._handle_state_changed
        )

    def async_stop(self) -> None:
        if self._unsub_state:
            self._unsub_state()
            self._unsub_state = None

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
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        self._points.append(point)
        self._store.async_delay_save(self._data_to_save, 5)

    @callback
    def _data_to_save(self) -> dict[str, Any]:
        return {"points": list(self._points)}

    def get_all(self) -> list[dict[str, Any]]:
        return list(self._points)

    def get_latest_per_person(self) -> list[dict[str, Any]]:
        latest: dict[str, dict[str, Any]] = {}
        for point in self._points:
            latest[point["entity_id"]] = point
        return list(latest.values())
