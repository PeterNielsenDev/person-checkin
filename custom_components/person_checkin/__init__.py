"""The Person Check-in (Grafana) integration."""
from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import (
    CONF_PG_DATABASE,
    CONF_PG_HOST,
    CONF_PG_PASSWORD,
    CONF_PG_PORT,
    CONF_PG_SSLMODE,
    CONF_PG_USER,
    DOMAIN,
)
from .coordinator import PersonLocationCoordinator
from .pg import PostgresStore

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[str] = ["sensor"]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Person Check-in from a config entry."""
    store = PostgresStore(
        host=entry.data[CONF_PG_HOST],
        port=entry.data[CONF_PG_PORT],
        database=entry.data[CONF_PG_DATABASE],
        user=entry.data[CONF_PG_USER],
        password=entry.data[CONF_PG_PASSWORD],
        sslmode=entry.data[CONF_PG_SSLMODE],
    )
    await store.async_connect()

    coordinator = PersonLocationCoordinator(hass, store)
    coordinator.mark_connected()
    coordinator.async_start()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {
        "store": store,
        "coordinator": coordinator,
    }

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if not await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        return False
    data = hass.data[DOMAIN].pop(entry.entry_id, None)
    if data:
        data["coordinator"].async_stop()
        await data["store"].async_close()
    return True
