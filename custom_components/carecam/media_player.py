"""Speaker for CareCam: TTS and audio playback over the local audio channel."""

from __future__ import annotations

import asyncio
import logging

from homeassistant.components import ffmpeg, media_source
from homeassistant.components.media_player import (
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    MediaPlayerState,
    MediaType,
    async_process_play_media_url,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import CareCamConfigEntry
from .entity import device_info
from .protocol import CareCamError

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: CareCamConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    async_add_entities([CareCamSpeaker(hass, entry)])


class CareCamSpeaker(MediaPlayerEntity):
    _attr_has_entity_name = True
    _attr_name = "Speaker"
    _attr_translation_key = "speaker"
    _attr_supported_features = MediaPlayerEntityFeature.PLAY_MEDIA
    _attr_media_content_type = MediaType.MUSIC

    def __init__(self, hass: HomeAssistant, entry: CareCamConfigEntry) -> None:
        self._entry = entry
        self._attr_unique_id = f"{entry.unique_id}_speaker"
        self._attr_device_info = device_info(entry)
        self._attr_state = MediaPlayerState.IDLE

    async def async_play_media(
        self, media_type: str, media_id: str, **kwargs: object
    ) -> None:
        if media_source.is_media_source_id(media_id):
            sourced = await media_source.async_resolve_media(
                self.hass, media_id, self.entity_id
            )
            media_id = sourced.url
        media_id = async_process_play_media_url(self.hass, media_id)
        # fetch the audio
        try:
            session = async_get_clientsession(self.hass)
            async with session.get(media_id) as resp:
                resp.raise_for_status()
                src = await resp.read()
        except Exception as err:  # noqa: BLE001
            raise HomeAssistantError(f"could not fetch audio: {err}") from err
        # convert to G.711 mu-law, 8 kHz, mono, raw
        mulaw = await self._to_mulaw(src)
        self._attr_state = MediaPlayerState.PLAYING
        self.async_write_ha_state()
        try:
            await self._entry.runtime_data.session.play_audio("hatts", mulaw)
        except CareCamError as err:
            raise HomeAssistantError(f"playback failed: {err}") from err
        finally:
            self._attr_state = MediaPlayerState.IDLE
            self.async_write_ha_state()

    async def _to_mulaw(self, src: bytes) -> bytes:
        binary = ffmpeg.get_ffmpeg_manager(self.hass).binary
        proc = await asyncio.create_subprocess_exec(
            binary,
            "-hide_banner", "-loglevel", "error",
            "-i", "pipe:0",
            "-ar", "8000", "-ac", "1", "-f", "mulaw", "pipe:1",
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        out, err = await proc.communicate(src)
        if proc.returncode or not out:
            raise HomeAssistantError(f"audio conversion failed: {err[:200]!r}")
        return out
