"""CareCam local integration: RTSP video + PTZ + lens switch, no cloud."""

from __future__ import annotations

from dataclasses import dataclass

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, Platform
from homeassistant.core import HomeAssistant

from .const import CONF_OWNER_TOKEN
from .coordinator import CareCamCoordinator
from .protocol import CareCamSession

PLATFORMS = [
    Platform.CAMERA,
    Platform.BUTTON,
    Platform.SELECT,
    Platform.NUMBER,
    Platform.SWITCH,
    Platform.SENSOR,
    Platform.MEDIA_PLAYER,
    Platform.TEXT,
]

type CareCamConfigEntry = ConfigEntry["CareCamData"]


@dataclass
class CareCamData:
    """Runtime data: one shared session per camera, plus a status coordinator."""

    session: CareCamSession
    coordinator: CareCamCoordinator


async def async_setup_entry(hass: HomeAssistant, entry: CareCamConfigEntry) -> bool:
    session = CareCamSession(entry.data[CONF_HOST], entry.data[CONF_OWNER_TOKEN])
    coordinator = CareCamCoordinator(hass, session)
    entry.runtime_data = CareCamData(session=session, coordinator=coordinator)
    # first read may fail if the camera is briefly busy; entities still load
    await coordinator.async_config_entry_first_refresh()
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: CareCamConfigEntry) -> bool:
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        await entry.runtime_data.session.close()
    return unloaded
