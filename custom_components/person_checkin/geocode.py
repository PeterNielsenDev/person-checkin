"""Best-effort reverse geocoding of coordinates via Nominatim's public API."""
from __future__ import annotations

import asyncio
import logging
import math
import time

import aiohttp

from .const import (
    GEOCODE_MIN_INTERVAL_SECONDS,
    GEOCODE_TIMEOUT_SECONDS,
    GEOCODE_USER_AGENT,
    NOMINATIM_REVERSE_URL,
)

_LOGGER = logging.getLogger(__name__)


def haversine_meters(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance between two lat/lon points, in meters."""
    radius = 6371000
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = (
        math.sin(dphi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    )
    return 2 * radius * math.asin(math.sqrt(a))


class NominatimRateLimiter:
    """Keeps requests to Nominatim's public instance at roughly 1/second."""

    def __init__(self, min_interval: float = GEOCODE_MIN_INTERVAL_SECONDS) -> None:
        self._min_interval = min_interval
        self._lock = asyncio.Lock()
        self._last_call = 0.0

    async def wait(self) -> None:
        async with self._lock:
            elapsed = time.monotonic() - self._last_call
            if elapsed < self._min_interval:
                await asyncio.sleep(self._min_interval - elapsed)
            self._last_call = time.monotonic()


async def async_reverse_geocode(
    session: aiohttp.ClientSession,
    rate_limiter: NominatimRateLimiter,
    latitude: float,
    longitude: float,
) -> str | None:
    """Look up a human-readable address for a point.

    Best-effort only: returns None on any error, timeout or unexpected
    response instead of raising, so a location point is never dropped or
    delayed because geocoding didn't work.
    """
    await rate_limiter.wait()
    try:
        async with session.get(
            NOMINATIM_REVERSE_URL,
            params={
                "format": "jsonv2",
                "lat": latitude,
                "lon": longitude,
                "zoom": 18,
                "addressdetails": 0,
            },
            headers={"User-Agent": GEOCODE_USER_AGENT},
            timeout=aiohttp.ClientTimeout(total=GEOCODE_TIMEOUT_SECONDS),
        ) as resp:
            if resp.status != 200:
                _LOGGER.debug(
                    "Nominatim returned status %s for reverse geocode", resp.status
                )
                return None
            data = await resp.json()
    except (aiohttp.ClientError, asyncio.TimeoutError) as err:
        _LOGGER.debug(
            "Reverse geocoding failed, continuing without an address: %s", err
        )
        return None

    return data.get("display_name")
