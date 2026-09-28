"""PTZ nudge buttons for CareCam."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import CareCamConfigEntry
from .entity import device_info
from .protocol import (
    PTZ_DOWN,
    PTZ_LEFT,
    PTZ_RIGHT,
    PTZ_UP,
    CareCamError,
)

DIRECTIONS = {
    "ptz_up": PTZ_UP,
    "ptz_down": PTZ_DOWN,
    "ptz_left": PTZ_LEFT,
    "ptz_right": PTZ_RIGHT,
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: CareCamConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    entities: list[ButtonEntity] = [
        CareCamPtzButton(entry, key, direction)
        for key, direction in DIRECTIONS.items()
    ]
    try:
        names = await entry.runtime_data.session.sound_list()
    except CareCamError:
        names = []
    entities += [CareCamSoundButton(entry, name) for name in names]
    entities += [
        CareCamMaintButton(
            entry, "reboot", "Reboot", "3412", {"ChannelID": 0}, "mdi:restart"
        ),
        CareCamMaintButton(
            entry, "factory_reset", "Factory reset", "3416", {}, "mdi:alert-octagon"
        ),
    ]
    async_add_entities(entities)


class CareCamPtzButton(ButtonEntity):
    _attr_has_entity_name = True

    def __init__(self, entry: CareCamConfigEntry, key: str, direction: str) -> None:
        self._entry = entry
        self._direction = direction
        self._attr_translation_key = key
        self._attr_name = key.replace("_", " ").upper().replace("PTZ ", "PTZ ")
        self._attr_unique_id = f"{entry.unique_id}_{key}"
        self._attr_device_info = device_info(entry)

    async def async_press(self) -> None:
        try:
            await self._entry.runtime_data.session.nudge(self._direction, 1.0)
        except CareCamError as err:
            raise HomeAssistantError(f"PTZ failed: {err}") from err


class CareCamMaintButton(ButtonEntity):
    """Reboot / factory reset. Disabled by default so it can't be hit by accident."""

    _attr_has_entity_name = True
    _attr_entity_registry_enabled_default = False

    def __init__(
        self,
        entry: CareCamConfigEntry,
        key: str,
        name: str,
        method: str,
        body: dict,
        icon: str,
    ) -> None:
        self._entry = entry
        self._method = method
        self._body = body
        self._attr_name = name
        self._attr_icon = icon
        self._attr_unique_id = f"{entry.unique_id}_{key}"
        self._attr_device_info = device_info(entry)

    async def async_press(self) -> None:
        try:
            await self._entry.runtime_data.session.send(self._method, self._body)
        except CareCamError as err:
            raise HomeAssistantError(f"{self._attr_name} failed: {err}") from err


class CareCamSoundButton(ButtonEntity):
    """Play a sound clip stored on the camera."""

    _attr_has_entity_name = True
    _attr_icon = "mdi:bullhorn"

    def __init__(self, entry: CareCamConfigEntry, name: str) -> None:
        self._entry = entry
        self._sound = name
        self._attr_name = f"Play sound {name}"
        self._attr_unique_id = f"{entry.unique_id}_sound_{name}"
        self._attr_device_info = device_info(entry)

    async def async_press(self) -> None:
        try:
            await self._entry.runtime_data.session.play_sound(self._sound)
        except CareCamError as err:
            raise HomeAssistantError(f"play sound failed: {err}") from err
