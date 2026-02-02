"""Base entity for z.ai Conversation integration."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.entity import Entity

from .const import CONF_CHAT_MODEL, DEFAULT, DOMAIN

if TYPE_CHECKING:
    import anthropic

    from homeassistant.config_entries import ConfigEntry

    type ZaiConfigEntry = ConfigEntry[anthropic.AsyncAnthropic]


class ZaiBaseLLMEntity(Entity):
    """Base entity for z.ai LLM entities."""

    _attr_has_entity_name = True

    def __init__(self, entry: ZaiConfigEntry, config_entry: ConfigEntry) -> None:
        """Initialize the entity."""
        self.entry = entry
        self._attr_unique_id = config_entry.entry_id

        self._attr_device_info = dr.DeviceInfo(
            identifiers={(DOMAIN, config_entry.entry_id)},
            name="z.ai",
            manufacturer="z.ai",
            model=config_entry.options.get(CONF_CHAT_MODEL, DEFAULT[CONF_CHAT_MODEL]),
            entry_type=dr.DeviceEntryType.SERVICE,
        )
