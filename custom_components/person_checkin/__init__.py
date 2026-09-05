"""The Person Check-in (Grafana) integration."""
from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .coordinator import PersonLocationStore
from .http import PersonLatestLocationView, PersonLocationsView

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[str] = []


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Person Check-in from a config entry."""
    store = PersonLocationStore(hass)
    await store.async_load()
    store.async_start()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = store

    if not hass.data[DOMAIN].get("_views_registered"):
        hass.http.register_view(PersonLocationsView(store))
        hass.http.register_view(PersonLatestLocationView(store))
        hass.data[DOMAIN]["_views_registered"] = True

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    store: PersonLocationStore = hass.data[DOMAIN].pop(entry.entry_id, None)
    if store:
        store.async_stop()
    return True
