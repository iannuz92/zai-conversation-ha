"""Base entity for z.ai Conversation integration."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.config_entries import ConfigSubentry
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

    def __init__(self, entry: ZaiConfigEntry, subentry: ConfigSubentry) -> None:
        """Initialize the entity."""
        self.entry = entry
        self.subentry = subentry
        self._attr_unique_id = subentry.subentry_id

        self._attr_device_info = dr.DeviceInfo(
            identifiers={(DOMAIN, subentry.subentry_id)},
            name=subentry.title,
            manufacturer="z.ai",
            model=subentry.data.get(CONF_CHAT_MODEL, DEFAULT[CONF_CHAT_MODEL]),
            entry_type=dr.DeviceEntryType.SERVICE,
        )
