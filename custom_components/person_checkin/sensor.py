"""Status sensor for Person Check-in (Grafana)."""
from __future__ import annotations

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import PersonLocationCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: PersonLocationCoordinator = hass.data[DOMAIN][entry.entry_id][
        "coordinator"
    ]
    async_add_entities([PersonCheckinStatusSensor(entry, coordinator)])


class PersonCheckinStatusSensor(SensorEntity):
    """Shows whether the integration is actually able to write to PostgreSQL."""

    _attr_has_entity_name = True
    _attr_name = "Status"
    _attr_icon = "mdi:map-marker-check"
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_should_poll = False

    def __init__(
        self, entry: ConfigEntry, coordinator: PersonLocationCoordinator
    ) -> None:
        self._coordinator = coordinator
        self._attr_unique_id = f"{entry.entry_id}_status"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "name": entry.title,
            "manufacturer": "Person Check-in",
            "entry_type": "service",
        }
        self._remove_listener = None

    async def async_added_to_hass(self) -> None:
        self._remove_listener = self._coordinator.async_add_listener(
            self._handle_update
        )

    async def async_will_remove_from_hass(self) -> None:
        if self._remove_listener:
            self._remove_listener()
            self._remove_listener = None

    @callback
    def _handle_update(self) -> None:
        self.async_write_ha_state()

    @property
    def native_value(self) -> str:
        if self._coordinator.last_success is None and self._coordinator.last_error is None:
            return "unknown"
        if self._coordinator.last_error_time and (
            self._coordinator.last_success is None
            or self._coordinator.last_error_time > self._coordinator.last_success
        ):
            return "error"
        return "ok"

    @property
    def extra_state_attributes(self) -> dict[str, str | int | None]:
        return {
            "last_success": (
                self._coordinator.last_success.isoformat()
                if self._coordinator.last_success
                else None
            ),
            "last_error": self._coordinator.last_error,
            "last_error_time": (
                self._coordinator.last_error_time.isoformat()
                if self._coordinator.last_error_time
                else None
            ),
            "pending_points": self._coordinator.pending_count,
        }
