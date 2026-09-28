"""RTSP camera entities (main + sub) for CareCam."""

from __future__ import annotations

import voluptuous as vol

from homeassistant.components.camera import Camera, CameraEntityFeature
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv, entity_platform
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import CareCamConfigEntry
from .const import (
    CONF_RTSP_PASS,
    CONF_RTSP_PORT,
    CONF_RTSP_USER,
    DEFAULT_RTSP_PASS,
    DEFAULT_RTSP_PORT,
    DEFAULT_RTSP_USER,
)
from .entity import device_info
from .protocol import PTZ_DOWN, PTZ_LEFT, PTZ_RIGHT, PTZ_UP, CareCamError

DIRECTIONS = {"up": PTZ_UP, "down": PTZ_DOWN, "left": PTZ_LEFT, "right": PTZ_RIGHT}
LENSES = {"wide": 0, "tele": 1}
ACTIONS = [*DIRECTIONS, "stop", *LENSES]

# profile0 = main (HD), profile1 = sub (SD); profile2 also exists (same lens)
PROFILES = {"main_stream": "profile0", "sub_stream": "profile1"}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: CareCamConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    async_add_entities(CareCamCamera(entry, key, path) for key, path in PROFILES.items())
    entity_platform.async_get_current_platform().async_register_entity_service(
        "ptz",
        {
            vol.Required("action"): vol.In(ACTIONS),
            # 0 = keep moving until "stop" (hold); > 0 = move that long, then stop
            vol.Optional("duration", default=0): vol.All(
                vol.Coerce(float), vol.Range(min=0, max=30)
            ),
        },
        "async_ptz",
    )


class CareCamCamera(Camera):
    _attr_has_entity_name = True
    _attr_supported_features = CameraEntityFeature.STREAM

    def __init__(self, entry: CareCamConfigEntry, key: str, path: str) -> None:
        super().__init__()
        d = entry.data
        user = d.get(CONF_RTSP_USER, DEFAULT_RTSP_USER)
        pw = d.get(CONF_RTSP_PASS, DEFAULT_RTSP_PASS)
        port = d.get(CONF_RTSP_PORT, DEFAULT_RTSP_PORT)
        self._url = f"rtsp://{user}:{pw}@{d[CONF_HOST]}:{port}/{path}"
        self._attr_translation_key = key
        self._attr_name = key.replace("_", " ").title()
        self._attr_unique_id = f"{entry.unique_id}_{key}"
        self._attr_device_info = device_info(entry)
        self._entry = entry

    async def stream_source(self) -> str:
        return self._url

    @property
    def use_stream_for_stills(self) -> bool:
        return True

    async def async_ptz(self, action: str, duration: float = 0) -> None:
        """Start/stop moving, nudge, or switch lens."""
        session = self._entry.runtime_data.session
        try:
            if action in LENSES:
                await session.set_lens(LENSES[action])
            elif action == "stop":
                await session.stop()
            elif duration > 0:
                await session.nudge(DIRECTIONS[action], duration)
            else:
                await session.move(DIRECTIONS[action])
        except CareCamError as err:
            raise HomeAssistantError(f"PTZ failed: {err}") from err
