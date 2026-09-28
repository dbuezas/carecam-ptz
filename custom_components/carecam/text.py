"""Name shown on the video (OSD) for CareCam."""

from __future__ import annotations

from homeassistant.components.text import TextEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import CareCamConfigEntry
from .coordinator import CareCamCoordinator
from .entity import device_info
from .protocol import CareCamError

M_OSD = "341c"


async def async_setup_entry(
    hass: HomeAssistant,
    entry: CareCamConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    async_add_entities([CareCamOsdName(entry.runtime_data.coordinator, entry)])


class CareCamOsdName(CoordinatorEntity[CareCamCoordinator], TextEntity):
    _attr_has_entity_name = True
    _attr_translation_key = "video_name"
    _attr_name = "Name on video"
    _attr_native_max = 32
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(
        self, coordinator: CareCamCoordinator, entry: CareCamConfigEntry
    ) -> None:
        super().__init__(coordinator)
        self._entry = entry
        self._attr_unique_id = f"{entry.unique_id}_video_name"
        self._attr_device_info = device_info(entry)

    def _cam(self) -> dict:
        return (self.coordinator.data or {}).get("camera") or {}

    @property
    def native_value(self) -> str | None:
        return self._cam().get("OSDName")

    async def async_set_value(self, value: str) -> None:
        position = int(self._cam().get("OSDPosition") or 0)
        try:
            await self._entry.runtime_data.session.send(
                M_OSD, {"Position": position, "Name": value}
            )
        except CareCamError as err:
            raise HomeAssistantError(f"set video name failed: {err}") from err
        await self.coordinator.async_request_refresh()
