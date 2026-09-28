"""Polls the CareCam's read-only status (network, SD card) for sensors."""

from __future__ import annotations

from datetime import timedelta
import logging
from typing import Any

from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .protocol import CareCamError, CareCamSession

_LOGGER = logging.getLogger(__name__)

# read-only queries that work on the local connection
M_NETWORK = "3472"
M_TFCARD = "344e"
M_CONFIG = "331c"  # config sync; ConfType 2 returns Device + Camera blocks
CONF_CAMERA = 2


class CareCamCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Reads status and the camera config (for real entity states)."""

    def __init__(self, hass, session: CareCamSession) -> None:
        super().__init__(
            hass, _LOGGER, name="carecam", update_interval=timedelta(minutes=2)
        )
        self._session = session

    async def _async_update_data(self) -> dict[str, Any]:
        data: dict[str, Any] = {}
        try:
            data["network"] = await self._session.send(M_NETWORK)
            data["tfcard"] = await self._session.send(M_TFCARD)
            cfg = await self._session.send(M_CONFIG, {"Items": [{"ConfType": CONF_CAMERA, "Sign": 0}]})
            data["camera"] = cfg.get("Camera", {})
            data["device"] = cfg.get("Device", {})
        except CareCamError as err:
            raise UpdateFailed(str(err)) from err
        return data
