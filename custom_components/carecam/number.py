"""Speaker volume for CareCam (state read back from the camera config)."""

from __future__ import annotations

from homeassistant.components.number import (
    NumberEntity,
    NumberMode,
    RestoreNumber,
)
from homeassistant.const import PERCENTAGE, EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import CareCamConfigEntry
from .coordinator import CareCamCoordinator
from .entity import device_info
from .protocol import CareCamError

M_SET_VOLUME = "34b0"


async def async_setup_entry(
    hass: HomeAssistant,
    entry: CareCamConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    async_add_entities(
        [
            CareCamVolume(entry.runtime_data.coordinator, entry),
            CareCamPtzSpeed(entry),
            CareCamPtzStep(entry),
        ]
    )


class CareCamPtzStep(RestoreNumber):
    """How far each PTZ tap moves (Step; 360 = a full turn)."""

    _attr_has_entity_name = True
    _attr_translation_key = "ptz_step"
    _attr_name = "PTZ step"
    _attr_native_min_value = 1
    _attr_native_max_value = 64
    _attr_native_step = 1
    _attr_mode = NumberMode.SLIDER
    _attr_icon = "mdi:arrow-expand-horizontal"
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, entry: CareCamConfigEntry) -> None:
        self._entry = entry
        self._attr_unique_id = f"{entry.unique_id}_ptz_step"
        self._attr_device_info = device_info(entry)
        self._attr_native_value = 8

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        last = await self.async_get_last_number_data()
        if last and last.native_value is not None:
            self._attr_native_value = last.native_value
        self._entry.runtime_data.session.step = str(int(self._attr_native_value))

    async def async_set_native_value(self, value: float) -> None:
        self._attr_native_value = value
        self._entry.runtime_data.session.step = str(int(value))
        self.async_write_ha_state()


class CareCamPtzSpeed(RestoreNumber):
    """How fast PTZ moves (1 slow .. 8 fast). Applied to the shared session."""

    _attr_has_entity_name = True
    _attr_translation_key = "ptz_speed"
    _attr_name = "PTZ speed"
    _attr_native_min_value = 1
    _attr_native_max_value = 8
    _attr_native_step = 1
    _attr_mode = NumberMode.SLIDER
    _attr_icon = "mdi:speedometer"
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, entry: CareCamConfigEntry) -> None:
        self._entry = entry
        self._attr_unique_id = f"{entry.unique_id}_ptz_speed"
        self._attr_device_info = device_info(entry)
        self._attr_native_value = 4

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        last = await self.async_get_last_number_data()
        if last and last.native_value is not None:
            self._attr_native_value = last.native_value
        self._entry.runtime_data.session.speed = str(int(self._attr_native_value))

    async def async_set_native_value(self, value: float) -> None:
        self._attr_native_value = value
        self._entry.runtime_data.session.speed = str(int(value))
        self.async_write_ha_state()


class CareCamVolume(CoordinatorEntity[CareCamCoordinator], NumberEntity):
    _attr_has_entity_name = True
    _attr_translation_key = "speaker_volume"
    _attr_name = "Speaker volume"
    _attr_native_min_value = 0
    _attr_native_max_value = 100
    _attr_native_step = 1
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_mode = NumberMode.SLIDER
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(
        self, coordinator: CareCamCoordinator, entry: CareCamConfigEntry
    ) -> None:
        super().__init__(coordinator)
        self._entry = entry
        self._attr_unique_id = f"{entry.unique_id}_speaker_volume"
        self._attr_device_info = device_info(entry)

    @property
    def native_value(self) -> float | None:
        cam = (self.coordinator.data or {}).get("camera") or {}
        v = cam.get("Volumn")  # firmware spells it "Volumn"
        try:
            return float(v)
        except (TypeError, ValueError):
            return None

    async def async_set_native_value(self, value: float) -> None:
        try:
            await self._entry.runtime_data.session.send(
                M_SET_VOLUME, {"Volume": int(value)}
            )
        except CareCamError as err:
            raise HomeAssistantError(f"set volume failed: {err}") from err
        await self.coordinator.async_request_refresh()
