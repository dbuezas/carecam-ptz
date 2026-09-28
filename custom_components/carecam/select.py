"""Lens switch (wide/tele) and night vision mode, with real read-back."""

from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import CareCamConfigEntry
from .coordinator import CareCamCoordinator
from .entity import device_info
from .protocol import CareCamError

LENSES = {"wide": 0, "tele": 1}

# IRRedMode values from the app (IRModeEnum)
NIGHT_VISION = {
    "auto": 0,
    "auto_no_lamp": 1,
    "full_color": 2,
    "natural": 3,
    "infrared": 4,
}
M_IR_MODE = "342e"

# InversionType (set via {Inversion, CamID}); values from InversionTypeEnum
ORIENTATION = {"normal": 1, "flip": 2, "mirror": 4, "flip_mirror": 8}
M_INVERSION = "341a"


async def async_setup_entry(
    hass: HomeAssistant,
    entry: CareCamConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data.coordinator
    async_add_entities(
        [
            CareCamLensSelect(coordinator, entry),
            CareCamNightVision(coordinator, entry),
            CareCamOrientation(coordinator, entry),
        ]
    )


class _Base(CoordinatorEntity[CareCamCoordinator], SelectEntity):
    _attr_has_entity_name = True

    def __init__(
        self, coordinator: CareCamCoordinator, entry: CareCamConfigEntry, key: str
    ) -> None:
        super().__init__(coordinator)
        self._entry = entry
        self._attr_unique_id = f"{entry.unique_id}_{key}"
        self._attr_device_info = device_info(entry)

    def _cam(self) -> dict:
        return (self.coordinator.data or {}).get("camera") or {}


class CareCamOrientation(_Base):
    _attr_translation_key = "orientation"
    _attr_name = "Image orientation"
    _attr_options = list(ORIENTATION)
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, coordinator, entry) -> None:
        super().__init__(coordinator, entry, "orientation")

    @property
    def current_option(self) -> str | None:
        cur = str(self._cam().get("InversionType"))
        return next((k for k, v in ORIENTATION.items() if str(v) == cur), None)

    async def async_select_option(self, option: str) -> None:
        try:
            await self._entry.runtime_data.session.send(
                M_INVERSION, {"Inversion": ORIENTATION[option], "CamID": 0}
            )
        except CareCamError as err:
            raise HomeAssistantError(f"orientation failed: {err}") from err
        await self.coordinator.async_request_refresh()


class CareCamLensSelect(_Base):
    _attr_translation_key = "lens"
    _attr_name = "Lens"
    _attr_options = list(LENSES)

    def __init__(self, coordinator, entry) -> None:
        super().__init__(coordinator, entry, "lens")

    @property
    def current_option(self) -> str | None:
        sensor = self._cam().get("Sensor") or {}
        cur = str(sensor.get("CurrentLenID"))
        return next((k for k, v in LENSES.items() if str(v) == cur), None)

    async def async_select_option(self, option: str) -> None:
        try:
            await self._entry.runtime_data.session.set_lens(LENSES[option])
        except CareCamError as err:
            raise HomeAssistantError(f"lens switch failed: {err}") from err
        await self.coordinator.async_request_refresh()


class CareCamNightVision(_Base):
    _attr_translation_key = "night_vision"
    _attr_name = "Night vision"
    _attr_options = list(NIGHT_VISION)
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, coordinator, entry) -> None:
        super().__init__(coordinator, entry, "night_vision")

    @property
    def current_option(self) -> str | None:
        cur = str(self._cam().get("IRRedMode"))
        return next((k for k, v in NIGHT_VISION.items() if str(v) == cur), None)

    async def async_select_option(self, option: str) -> None:
        try:
            await self._entry.runtime_data.session.send(
                M_IR_MODE, {"IRRedMode": NIGHT_VISION[option]}
            )
        except CareCamError as err:
            raise HomeAssistantError(f"night vision failed: {err}") from err
        await self.coordinator.async_request_refresh()
