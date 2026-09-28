"""On/off controls for CareCam: privacy (camera off), microphone, WDR.

State is read back from the camera's config (via the coordinator).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import CareCamConfigEntry
from .coordinator import CareCamCoordinator
from .entity import device_info
from .protocol import CareCamError


@dataclass(frozen=True, kw_only=True)
class CareCamSwitch:
    key: str
    name: str
    method: str
    body: Callable[[bool], dict[str, Any]]
    # read the current on/off state from the Camera config block
    state: Callable[[dict], bool | None]
    icon: str | None = None


def _is_one(field: str) -> Callable[[dict], bool | None]:
    def read(cam: dict) -> bool | None:
        v = cam.get(field)
        return None if v is None else str(v) == "1"

    return read


SWITCHES: tuple[CareCamSwitch, ...] = (
    CareCamSwitch(
        key="camera_enabled",
        name="Camera enabled",
        method="341e",
        body=lambda on: {"CamStatus": 1 if on else 0},
        state=_is_one("CamStatus"),
        icon="mdi:cctv",
    ),
    CareCamSwitch(
        key="microphone",
        name="Microphone",
        method="3434",
        body=lambda on: {"MicroPhoneStatus": 1 if on else 0},
        state=_is_one("MicroPhoneStatus"),
        icon="mdi:microphone",
    ),
    CareCamSwitch(
        key="wide_dynamic_range",
        name="Wide dynamic range",
        method="346e",
        body=lambda on: {"Status": 1 if on else 0},
        state=_is_one("WDRMode"),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: CareCamConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data.coordinator
    async_add_entities(CareCamSwitchEntity(coordinator, entry, s) for s in SWITCHES)


class CareCamSwitchEntity(CoordinatorEntity[CareCamCoordinator], SwitchEntity):
    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(
        self,
        coordinator: CareCamCoordinator,
        entry: CareCamConfigEntry,
        spec: CareCamSwitch,
    ) -> None:
        super().__init__(coordinator)
        self._entry = entry
        self._spec = spec
        self._attr_translation_key = spec.key
        self._attr_name = spec.name
        self._attr_icon = spec.icon
        self._attr_unique_id = f"{entry.unique_id}_{spec.key}"
        self._attr_device_info = device_info(entry)

    @property
    def is_on(self) -> bool | None:
        cam = (self.coordinator.data or {}).get("camera") or {}
        return self._spec.state(cam)

    async def _apply(self, on: bool) -> None:
        try:
            await self._entry.runtime_data.session.send(
                self._spec.method, self._spec.body(on)
            )
        except CareCamError as err:
            raise HomeAssistantError(f"{self._spec.name} failed: {err}") from err
        await self.coordinator.async_request_refresh()

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self._apply(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self._apply(False)
