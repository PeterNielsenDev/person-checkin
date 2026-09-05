"""Minimal async client for the parts of the Grafana HTTP API this integration needs."""
from __future__ import annotations

import logging
from typing import Any

import aiohttp

from .const import DATASOURCE_NAME, DATASOURCE_TYPE

_LOGGER = logging.getLogger(__name__)


class GrafanaApiError(Exception):
    """Base error talking to Grafana."""


class GrafanaAuthError(GrafanaApiError):
    """Wrong username/password."""


class GrafanaConnectionError(GrafanaApiError):
    """Could not reach the Grafana server."""


class GrafanaClient:
    """Thin wrapper around Grafana's HTTP API using basic auth."""

    def __init__(
        self,
        session: aiohttp.ClientSession,
        host: str,
        port: int,
        username: str,
        password: str,
        use_ssl: bool = False,
        verify_ssl: bool = True,
    ) -> None:
        scheme = "https" if use_ssl else "http"
        self._base_url = f"{scheme}://{host}:{port}"
        self._session = session
        self._auth = aiohttp.BasicAuth(username, password)
        self._ssl = None if verify_ssl else False

    async def _request(
        self, method: str, path: str, json: dict[str, Any] | None = None
    ) -> Any:
        url = f"{self._base_url}{path}"
        try:
            async with self._session.request(
                method,
                url,
                json=json,
                auth=self._auth,
                ssl=self._ssl,
                timeout=aiohttp.ClientTimeout(total=15),
            ) as resp:
                if resp.status == 401:
                    raise GrafanaAuthError("Invalid Grafana username/password")
                if resp.status >= 400:
                    body = await resp.text()
                    raise GrafanaApiError(
                        f"Grafana returned {resp.status} for {method} {path}: {body}"
                    )
                if resp.content_type == "application/json":
                    return await resp.json()
                return await resp.text()
        except aiohttp.ClientConnectorError as err:
            raise GrafanaConnectionError(str(err)) from err
        except aiohttp.ClientError as err:
            raise GrafanaApiError(str(err)) from err

    async def test_connection(self) -> None:
        """Raise if we can't authenticate against Grafana."""
        await self._request("GET", "/api/org")

    async def list_dashboards(self) -> list[dict[str, Any]]:
        """Return [{uid, title}, ...] for all dashboards."""
        result = await self._request("GET", "/api/search?type=dash-db")
        return [{"uid": item["uid"], "title": item["title"]} for item in result]

    async def get_dashboard(self, uid: str) -> dict[str, Any]:
        return await self._request("GET", f"/api/dashboards/uid/{uid}")

    async def is_plugin_installed(self, plugin_id: str = DATASOURCE_TYPE) -> bool:
        try:
            await self._request("GET", f"/api/plugins/{plugin_id}/settings")
            return True
        except GrafanaApiError:
            return False

    async def get_or_create_datasource(self, ha_url: str, ha_token: str) -> str:
        """Ensure the Infinity datasource pointing at Home Assistant exists. Returns its uid."""
        try:
            existing = await self._request(
                "GET", f"/api/datasources/name/{DATASOURCE_NAME}"
            )
            return existing["uid"]
        except GrafanaApiError:
            pass

        payload = {
            "name": DATASOURCE_NAME,
            "type": DATASOURCE_TYPE,
            "access": "proxy",
            "url": ha_url,
            "jsonData": {
                "datasourceSecureJson": False,
                "auth_method": "bearerToken",
            },
            "secureJsonData": {
                "bearerToken": ha_token,
            },
        }
        result = await self._request("POST", "/api/datasources", json=payload)
        return result["datasource"]["uid"]

    def _geomap_panel(self, datasource_uid: str, panel_id: int) -> dict[str, Any]:
        return {
            "id": panel_id,
            "type": "geomap",
            "title": "Person locations",
            "gridPos": {"h": 14, "w": 24, "x": 0, "y": 0},
            "datasource": {"type": DATASOURCE_TYPE, "uid": datasource_uid},
            "targets": [
                {
                    "type": "json",
                    "source": "url",
                    "url": "${__datasource.url}/api/person_checkin/latest",
                    "url_options": {"method": "GET"},
                    "format": "table",
                    "root_selector": "",
                    "columns": [
                        {"selector": "name", "text": "name", "type": "string"},
                        {"selector": "state", "text": "state", "type": "string"},
                        {
                            "selector": "latitude",
                            "text": "latitude",
                            "type": "number",
                        },
                        {
                            "selector": "longitude",
                            "text": "longitude",
                            "type": "number",
                        },
                        {
                            "selector": "timestamp",
                            "text": "time",
                            "type": "timestamp",
                        },
                    ],
                    "refId": "A",
                }
            ],
            "options": {
                "view": {"id": "zero", "lat": 0, "lon": 0, "zoom": 3},
                "layers": [
                    {
                        "type": "markers",
                        "name": "Persons",
                        "config": {
                            "style": {
                                "size": {"fixed": 6},
                                "color": {"fixed": "dark-orange"},
                            },
                            "showLegend": True,
                        },
                        "location": {
                            "mode": "coords",
                            "latitude": "latitude",
                            "longitude": "longitude",
                        },
                    }
                ],
            },
        }

    def _table_panel(self, datasource_uid: str, panel_id: int) -> dict[str, Any]:
        return {
            "id": panel_id,
            "type": "table",
            "title": "Location history",
            "gridPos": {"h": 10, "w": 24, "x": 0, "y": 14},
            "datasource": {"type": DATASOURCE_TYPE, "uid": datasource_uid},
            "targets": [
                {
                    "type": "json",
                    "source": "url",
                    "url": "${__datasource.url}/api/person_checkin/locations",
                    "url_options": {"method": "GET"},
                    "format": "table",
                    "root_selector": "",
                    "columns": [
                        {"selector": "name", "text": "name", "type": "string"},
                        {"selector": "state", "text": "state", "type": "string"},
                        {
                            "selector": "latitude",
                            "text": "latitude",
                            "type": "number",
                        },
                        {
                            "selector": "longitude",
                            "text": "longitude",
                            "type": "number",
                        },
                        {
                            "selector": "gps_accuracy",
                            "text": "gps_accuracy",
                            "type": "number",
                        },
                        {
                            "selector": "timestamp",
                            "text": "time",
                            "type": "timestamp",
                        },
                    ],
                    "refId": "A",
                }
            ],
            "options": {"sortBy": [{"displayName": "time", "desc": True}]},
        }

    async def create_dashboard(self, title: str, datasource_uid: str) -> str:
        """Create a brand new dashboard with a geomap + history panel. Returns its uid."""
        dashboard = {
            "id": None,
            "uid": None,
            "title": title,
            "timezone": "browser",
            "schemaVersion": 39,
            "refresh": "30s",
            "panels": [
                self._geomap_panel(datasource_uid, 1),
                self._table_panel(datasource_uid, 2),
            ],
        }
        result = await self._request(
            "POST",
            "/api/dashboards/db",
            json={"dashboard": dashboard, "overwrite": False, "message": "Created by Person Check-in"},
        )
        return result["uid"]

    async def add_panels_to_dashboard(self, uid: str, datasource_uid: str) -> None:
        """Append the geomap + history panels to an existing dashboard."""
        current = await self.get_dashboard(uid)
        dashboard = current["dashboard"]
        panels = dashboard.get("panels", [])
        next_id = max((p.get("id", 0) for p in panels), default=0) + 1
        max_y = max(
            (p.get("gridPos", {}).get("y", 0) + p.get("gridPos", {}).get("h", 0) for p in panels),
            default=0,
        )
        geomap = self._geomap_panel(datasource_uid, next_id)
        geomap["gridPos"]["y"] = max_y
        table = self._table_panel(datasource_uid, next_id + 1)
        table["gridPos"]["y"] = max_y + geomap["gridPos"]["h"]
        panels.extend([geomap, table])
        dashboard["panels"] = panels

        await self._request(
            "POST",
            "/api/dashboards/db",
            json={
                "dashboard": dashboard,
                "overwrite": True,
                "message": "Added Person Check-in panels",
            },
        )
