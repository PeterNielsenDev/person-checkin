"""Config flow for Person Check-in (Grafana)."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import (
    CONF_DASHBOARD_TITLE,
    CONF_DASHBOARD_UID,
    CONF_DATASOURCE_UID,
    CONF_HA_TOKEN,
    CONF_HA_URL,
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_USE_SSL,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
    CREATE_NEW_DASHBOARD,
    DEFAULT_PORT,
    DEFAULT_USE_SSL,
    DEFAULT_VERIFY_SSL,
    DOMAIN,
)
from .grafana_api import GrafanaAuthError, GrafanaClient, GrafanaConnectionError

_LOGGER = logging.getLogger(__name__)


class PersonCheckinConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle the setup wizard."""

    VERSION = 1

    def __init__(self) -> None:
        self._data: dict[str, Any] = {}
        self._dashboards: list[dict[str, str]] = []

    def _make_client(self) -> GrafanaClient:
        session = async_get_clientsession(self.hass, verify_ssl=self._data.get(CONF_VERIFY_SSL, True))
        return GrafanaClient(
            session,
            host=self._data[CONF_HOST],
            port=self._data[CONF_PORT],
            username=self._data[CONF_USERNAME],
            password=self._data[CONF_PASSWORD],
            use_ssl=self._data[CONF_USE_SSL],
            verify_ssl=self._data.get(CONF_VERIFY_SSL, True),
        )

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.FlowResult:
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")

        errors: dict[str, str] = {}
        if user_input is not None:
            self._data.update(user_input)
            client = self._make_client()
            try:
                await client.test_connection()
            except GrafanaAuthError:
                errors["base"] = "invalid_auth"
            except GrafanaConnectionError:
                errors["base"] = "cannot_connect"
            except Exception:  # noqa: BLE001
                _LOGGER.exception("Unexpected error validating Grafana connection")
                errors["base"] = "unknown"
            else:
                return await self.async_step_ha_connection()

        schema = vol.Schema(
            {
                vol.Required(CONF_HOST): str,
                vol.Required(CONF_PORT, default=DEFAULT_PORT): int,
                vol.Required(CONF_USE_SSL, default=DEFAULT_USE_SSL): bool,
                vol.Required(CONF_VERIFY_SSL, default=DEFAULT_VERIFY_SSL): bool,
                vol.Required(CONF_USERNAME): str,
                vol.Required(CONF_PASSWORD): str,
            }
        )
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)

    async def async_step_ha_connection(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.FlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            self._data.update(user_input)
            try:
                client = self._make_client()
                self._data[CONF_DATASOURCE_UID] = await client.get_or_create_datasource(
                    self._data[CONF_HA_URL], self._data[CONF_HA_TOKEN]
                )
            except Exception:  # noqa: BLE001
                _LOGGER.exception("Failed to create Grafana datasource")
                errors["base"] = "datasource_failed"
            else:
                return await self.async_step_dashboard()

        default_url = (
            self.hass.config.external_url
            or self.hass.config.internal_url
            or "http://homeassistant.local:8123"
        )
        schema = vol.Schema(
            {
                vol.Required(CONF_HA_URL, default=default_url): str,
                vol.Required(CONF_HA_TOKEN): str,
            }
        )
        return self.async_show_form(
            step_id="ha_connection", data_schema=schema, errors=errors
        )

    async def async_step_dashboard(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.FlowResult:
        errors: dict[str, str] = {}
        client = self._make_client()

        if not self._dashboards:
            try:
                self._dashboards = await client.list_dashboards()
            except Exception:  # noqa: BLE001
                _LOGGER.exception("Failed to list Grafana dashboards")
                errors["base"] = "cannot_connect"

        if user_input is not None and not errors:
            selection = user_input[CONF_DASHBOARD_UID]
            if selection == CREATE_NEW_DASHBOARD:
                self._data[CONF_DASHBOARD_TITLE] = user_input.get(
                    CONF_DASHBOARD_TITLE, "Person Check-in"
                )
                return await self._create_new_dashboard(client)
            return await self._use_existing_dashboard(client, selection)

        return self.async_show_form(
            step_id="dashboard", data_schema=self._dashboard_schema(), errors=errors
        )

    def _dashboard_schema(self) -> vol.Schema:
        options = {CREATE_NEW_DASHBOARD: "➕ Opret nyt dashboard"}
        options.update({d["uid"]: d["title"] for d in self._dashboards})
        return vol.Schema(
            {
                vol.Required(CONF_DASHBOARD_UID, default=CREATE_NEW_DASHBOARD): vol.In(
                    options
                ),
                vol.Optional(CONF_DASHBOARD_TITLE, default="Person Check-in"): str,
            }
        )

    async def _create_new_dashboard(
        self, client: GrafanaClient
    ) -> config_entries.FlowResult:
        try:
            uid = await client.create_dashboard(
                self._data[CONF_DASHBOARD_TITLE], self._data[CONF_DATASOURCE_UID]
            )
        except Exception:  # noqa: BLE001
            _LOGGER.exception("Failed to create Grafana dashboard")
            return self.async_show_form(
                step_id="dashboard",
                data_schema=self._dashboard_schema(),
                errors={"base": "dashboard_failed"},
            )
        self._data[CONF_DASHBOARD_UID] = uid
        return self.async_create_entry(
            title=f"Grafana ({self._data[CONF_HOST]})", data=self._data
        )

    async def _use_existing_dashboard(
        self, client: GrafanaClient, uid: str
    ) -> config_entries.FlowResult:
        try:
            await client.add_panels_to_dashboard(uid, self._data[CONF_DATASOURCE_UID])
        except Exception:  # noqa: BLE001
            _LOGGER.exception("Failed to add panels to existing Grafana dashboard")
            return self.async_show_form(
                step_id="dashboard",
                data_schema=self._dashboard_schema(),
                errors={"base": "dashboard_failed"},
            )
        self._data[CONF_DASHBOARD_UID] = uid
        return self.async_create_entry(
            title=f"Grafana ({self._data[CONF_HOST]})", data=self._data
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        return PersonCheckinOptionsFlow(config_entry)


class PersonCheckinOptionsFlow(config_entries.OptionsFlow):
    """Allow re-running the dashboard picker later."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        self.config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.FlowResult:
        return self.async_create_entry(title="", data={})
