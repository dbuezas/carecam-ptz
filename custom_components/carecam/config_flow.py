"""Config flow for CareCam: host + OwnerToken (+ optional RTSP login)."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_NAME

from .const import (
    CONF_OWNER_TOKEN,
    CONF_RTSP_PASS,
    CONF_RTSP_PORT,
    CONF_RTSP_USER,
    DEFAULT_RTSP_PASS,
    DEFAULT_RTSP_PORT,
    DEFAULT_RTSP_USER,
    DOMAIN,
)
from .protocol import CareCamError, async_check


class CareCamConfigFlow(ConfigFlow, domain=DOMAIN):
    """Ask for the camera address and its OwnerToken, then verify a local login."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                await async_check(
                    user_input[CONF_HOST], user_input[CONF_OWNER_TOKEN]
                )
            except CareCamError:
                errors["base"] = "cannot_connect"
            else:
                await self.async_set_unique_id(user_input[CONF_OWNER_TOKEN])
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=user_input.get(CONF_NAME) or user_input[CONF_HOST],
                    data=user_input,
                )

        schema = vol.Schema(
            {
                vol.Required(CONF_NAME, default="CareCam"): str,
                vol.Required(CONF_HOST): str,
                vol.Required(CONF_OWNER_TOKEN): str,
                vol.Optional(CONF_RTSP_USER, default=DEFAULT_RTSP_USER): str,
                vol.Optional(CONF_RTSP_PASS, default=DEFAULT_RTSP_PASS): str,
                vol.Optional(CONF_RTSP_PORT, default=DEFAULT_RTSP_PORT): int,
            }
        )
        return self.async_show_form(
            step_id="user", data_schema=schema, errors=errors
        )
