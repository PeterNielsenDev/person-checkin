"""Minimal async client for the parts of the Grafana HTTP API this integration needs."""
from __future__ import annotations

import logging
from typing import Any

import aiohttp

from .const import DATASOURCE_TYPE, TABLE_NAME

_LOGGER = logging.getLogger(__name__)


class GrafanaApiError(Exception):
    """Base error talking to Grafana."""


class GrafanaAuthError(GrafanaApiError):
    """Invalid or insufficiently privileged service account token."""


class GrafanaConnectionError(GrafanaApiError):
    """Could not reach the Grafana server."""


class GrafanaClient:
    """Thin wrapper around Grafana's HTTP API using a service account token.

    Only calls endpoints a service account with the Editor role can use
    (dashboard search/read/write). Managing data sources requires the Admin
    role in Grafana, so the PostgreSQL datasource must already exist and its
    uid is supplied by the user instead of being created/looked up here.
    """

    def __init__(
        self,
        session: aiohttp.ClientSession,
        host: str,
        port: int,
        api_token: str,
        use_ssl: bool = False,
        verify_ssl: bool = True,
    ) -> None:
        scheme = "https" if use_ssl else "http"
        self._base_url = f"{scheme}://{host}:{port}"
        self._session = session
        self._headers = {"Authorization": f"Bearer {api_token}"}
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
                headers=self._headers,
                ssl=self._ssl,
                timeout=aiohttp.ClientTimeout(total=15),
            ) as resp:
                if resp.status in (401, 403):
                    raise GrafanaAuthError("Invalid or insufficiently privileged Grafana service account token")
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
        """Raise if we can't authenticate against Grafana.

        Uses dashboard search rather than an admin-only endpoint, since this
        must succeed for a service account token with only the Editor role.
        """
        await self._request("GET", "/api/search?limit=1")

    async def list_dashboards(self) -> list[dict[str, Any]]:
        """Return [{uid, title}, ...] for all dashboards."""
        result = await self._request("GET", "/api/search?type=dash-db")
        return [{"uid": item["uid"], "title": item["title"]} for item in result]

    async def get_dashboard(self, uid: str) -> dict[str, Any]:
        return await self._request("GET", f"/api/dashboards/uid/{uid}")

    def _geomap_panel(self, datasource_uid: str, panel_id: int) -> dict[str, Any]:
        raw_sql = (
            "SELECT DISTINCT ON (entity_id)\n"
            "  entity_id, name, state, latitude, longitude, address, \"time\"\n"
            f"FROM {TABLE_NAME}\n"
            "ORDER BY entity_id, \"time\" DESC"
        )
        return {
            "id": panel_id,
            "type": "geomap",
            "title": "Person locations",
            "gridPos": {"h": 14, "w": 24, "x": 0, "y": 0},
            "datasource": {"type": DATASOURCE_TYPE, "uid": datasource_uid},
            "targets": [
                {
                    "rawSql": raw_sql,
                    "format": "table",
                    "rawQuery": True,
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
        raw_sql = (
            "SELECT name, state, latitude, longitude, gps_accuracy, address, \"time\"\n"
            f"FROM {TABLE_NAME}\n"
            "WHERE $__timeFilter(\"time\")\n"
            "ORDER BY \"time\" DESC\n"
            "LIMIT 500"
        )
        return {
            "id": panel_id,
            "type": "table",
            "title": "Location history",
            "gridPos": {"h": 10, "w": 24, "x": 0, "y": 14},
            "datasource": {"type": DATASOURCE_TYPE, "uid": datasource_uid},
            "targets": [
                {
                    "rawSql": raw_sql,
                    "format": "table",
                    "rawQuery": True,
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
