"""Shared device info for CareCam entities."""

from __future__ import annotations

from homeassistant.const import CONF_HOST
from homeassistant.helpers.device_registry import DeviceInfo

from . import CareCamConfigEntry
from .const import DOMAIN


def device_info(entry: CareCamConfigEntry) -> DeviceInfo:
    return DeviceInfo(
        identifiers={(DOMAIN, entry.unique_id or entry.entry_id)},
        name=entry.title,
        manufacturer="YGTek / Huiyun (CareCam)",
        configuration_url=None,
        connections=set(),
        model="CareCam",
    )
