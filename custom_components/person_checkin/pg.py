"""Minimal async PostgreSQL client for storing location points."""
from __future__ import annotations

import logging
from typing import Any

import asyncpg

from .const import TABLE_NAME

_LOGGER = logging.getLogger(__name__)

_CREATE_TABLE_SQL = f"""
CREATE TABLE IF NOT EXISTS {TABLE_NAME} (
    id BIGSERIAL PRIMARY KEY,
    entity_id TEXT NOT NULL,
    name TEXT,
    state TEXT,
    latitude DOUBLE PRECISION NOT NULL,
    longitude DOUBLE PRECISION NOT NULL,
    gps_accuracy DOUBLE PRECISION,
    source TEXT,
    address TEXT,
    "time" TIMESTAMPTZ NOT NULL DEFAULT now()
);
"""

# Installs from before the address column existed need it added on top of
# their existing table - CREATE TABLE IF NOT EXISTS alone won't do that.
_ADD_ADDRESS_COLUMN_SQL = f"""
ALTER TABLE {TABLE_NAME} ADD COLUMN IF NOT EXISTS address TEXT;
"""

_CREATE_INDEX_TIME_SQL = f"""
CREATE INDEX IF NOT EXISTS idx_{TABLE_NAME}_time ON {TABLE_NAME} ("time");
"""

_CREATE_INDEX_ENTITY_TIME_SQL = f"""
CREATE INDEX IF NOT EXISTS idx_{TABLE_NAME}_entity_time
    ON {TABLE_NAME} (entity_id, "time" DESC);
"""

_INSERT_SQL = f"""
INSERT INTO {TABLE_NAME}
    (entity_id, name, state, latitude, longitude, gps_accuracy, source, address, "time")
VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
"""


class PostgresError(Exception):
    """Wraps any error talking to PostgreSQL."""


async def test_connection(
    host: str, port: int, database: str, user: str, password: str, sslmode: str
) -> None:
    """Raise PostgresError if we can't connect with the given credentials."""
    try:
        conn = await asyncpg.connect(
            host=host,
            port=port,
            database=database,
            user=user,
            password=password,
            ssl=None if sslmode == "disable" else sslmode,
            timeout=10,
        )
    except Exception as err:  # noqa: BLE001
        raise PostgresError(str(err)) from err
    await conn.close()


class PostgresStore:
    """Pooled async access to the person_checkin_locations table."""

    def __init__(
        self,
        host: str,
        port: int,
        database: str,
        user: str,
        password: str,
        sslmode: str,
    ) -> None:
        self._host = host
        self._port = port
        self._database = database
        self._user = user
        self._password = password
        self._sslmode = sslmode
        self._pool: asyncpg.Pool | None = None

    async def async_connect(self) -> None:
        self._pool = await asyncpg.create_pool(
            host=self._host,
            port=self._port,
            database=self._database,
            user=self._user,
            password=self._password,
            ssl=None if self._sslmode == "disable" else self._sslmode,
            min_size=1,
            max_size=5,
        )
        async with self._pool.acquire() as conn:
            await conn.execute(_CREATE_TABLE_SQL)
            await conn.execute(_ADD_ADDRESS_COLUMN_SQL)
            await conn.execute(_CREATE_INDEX_TIME_SQL)
            await conn.execute(_CREATE_INDEX_ENTITY_TIME_SQL)

    async def async_close(self) -> None:
        if self._pool is not None:
            await self._pool.close()
            self._pool = None

    async def async_insert_point(self, point: dict[str, Any]) -> None:
        if self._pool is None:
            raise PostgresError("Postgres pool is not connected")
        try:
            async with self._pool.acquire() as conn:
                await conn.execute(
                    _INSERT_SQL,
                    point["entity_id"],
                    point["name"],
                    point["state"],
                    point["latitude"],
                    point["longitude"],
                    point["gps_accuracy"],
                    point["source"],
                    point.get("address"),
                    point["timestamp"],
                )
        except Exception as err:  # noqa: BLE001
            raise PostgresError(str(err)) from err
