"""The z.ai Conversation integration."""

from __future__ import annotations

from functools import partial
import logging
from typing import TYPE_CHECKING

import anthropic

from homeassistant.config_entries import ConfigEntry, ConfigSubentry
from homeassistant.const import CONF_API_KEY, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .const import CONF_BASE_URL, DEFAULT_BASE_URL, DOMAIN

type ZaiConfigEntry = ConfigEntry[anthropic.AsyncAnthropic]

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.CONVERSATION]

__all__ = ["ZaiConfigEntry"]


async def async_setup_entry(hass: HomeAssistant, entry: ZaiConfigEntry) -> bool:
    """Set up z.ai Conversation from a config entry."""
    api_key = entry.data[CONF_API_KEY]
    base_url = entry.data.get(CONF_BASE_URL, DEFAULT_BASE_URL)

    try:
        client = await hass.async_add_executor_job(
            partial(
                anthropic.AsyncAnthropic,
                api_key=api_key,
                base_url=base_url,
                default_headers={"x-api-key": api_key},
            )
        )
    except Exception as err:
        _LOGGER.exception("Error setting up z.ai client: %s", err)
        raise ConfigEntryNotReady from err

    entry.runtime_data = client

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_remove_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle removal of an entry."""
    # Cleanup subentries if any
    pass


async def async_remove_config_entry_device(
    hass: HomeAssistant, config_entry: ConfigEntry, device_entry
) -> bool:
    """Remove a config entry from a device."""
    return True
