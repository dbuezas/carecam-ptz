"""Diagnostic sensors for CareCam: WiFi signal, SD card."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.const import PERCENTAGE, EntityCategory, UnitOfInformation
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import CareCamConfigEntry
from .coordinator import CareCamCoordinator
from .entity import device_info

CARD_STATES = {"0": "no_card", "1": "normal", "2": "no_card", "3": "error"}


def _mb(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


@dataclass(frozen=True, kw_only=True)
class CareCamSensor:
    key: str
    name: str
    group: str  # "network" or "tfcard"
    value: Callable[[dict], Any]
    unit: str | None = None
    device_class: SensorDeviceClass | None = None
    state_class: SensorStateClass | None = None
    icon: str | None = None


SENSORS: tuple[CareCamSensor, ...] = (
    CareCamSensor(
        key="wifi_signal",
        name="WiFi signal",
        group="network",
        value=lambda d: _mb(d.get("Signal")),
        unit=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:wifi",
    ),
    CareCamSensor(
        key="sd_total",
        name="SD card size",
        group="tfcard",
        value=lambda d: _mb(d.get("TotalSize")),
        unit=UnitOfInformation.MEGABYTES,
        device_class=SensorDeviceClass.DATA_SIZE,
        icon="mdi:sd",
    ),
    CareCamSensor(
        key="sd_free",
        name="SD card free",
        group="tfcard",
        value=lambda d: _mb(d.get("FreeSize")),
        unit=UnitOfInformation.MEGABYTES,
        device_class=SensorDeviceClass.DATA_SIZE,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:sd",
    ),
    CareCamSensor(
        key="sd_status",
        name="SD card status",
        group="tfcard",
        value=lambda d: CARD_STATES.get(str(d.get("CardStatus")), "unknown"),
        icon="mdi:sd",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: CareCamConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data.coordinator
    async_add_entities(CareCamSensorEntity(coordinator, entry, s) for s in SENSORS)


class CareCamSensorEntity(CoordinatorEntity[CareCamCoordinator], SensorEntity):
    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(
        self,
        coordinator: CareCamCoordinator,
        entry: CareCamConfigEntry,
        spec: CareCamSensor,
    ) -> None:
        super().__init__(coordinator)
        self._spec = spec
        self._attr_translation_key = spec.key
        self._attr_name = spec.name
        self._attr_icon = spec.icon
        self._attr_native_unit_of_measurement = spec.unit
        self._attr_device_class = spec.device_class
        self._attr_state_class = spec.state_class
        self._attr_unique_id = f"{entry.unique_id}_{spec.key}"
        self._attr_device_info = device_info(entry)

    @property
    def native_value(self) -> Any:
        group = (self.coordinator.data or {}).get(self._spec.group) or {}
        return self._spec.value(group)
