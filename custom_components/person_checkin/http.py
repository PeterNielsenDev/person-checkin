"""HTTP views exposing tracked person locations for Grafana to poll."""
from __future__ import annotations

from aiohttp import web
from homeassistant.components.http import HomeAssistantView

from .const import LATEST_VIEW_URL, LOCATIONS_VIEW_URL
from .coordinator import PersonLocationStore


class PersonLocationsView(HomeAssistantView):
    """Full location history, newest last."""

    url = LOCATIONS_VIEW_URL
    name = "api:person_checkin:locations"
    requires_auth = True

    def __init__(self, store: PersonLocationStore) -> None:
        self._store = store

    async def get(self, request: web.Request) -> web.Response:
        return self.json(self._store.get_all())


class PersonLatestLocationView(HomeAssistantView):
    """Most recent known location per person, for a live map panel."""

    url = LATEST_VIEW_URL
    name = "api:person_checkin:latest"
    requires_auth = True

    def __init__(self, store: PersonLocationStore) -> None:
        self._store = store

    async def get(self, request: web.Request) -> web.Response:
        return self.json(self._store.get_latest_per_person())
