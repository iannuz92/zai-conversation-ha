"""Device context builder for z.ai Conversation."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.core import HomeAssistant, State
from homeassistant.helpers import area_registry as ar
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er

_LOGGER = logging.getLogger(__name__)

# Relevant attributes per domain - only these will be included in context
DOMAIN_RELEVANT_ATTRS: dict[str, list[str]] = {
    "light": ["brightness", "color_temp", "rgb_color", "color_mode", "effect"],
    "switch": [],
    "climate": [
        "temperature",
        "current_temperature",
        "target_temperature",
        "hvac_modes",
        "hvac_action",
        "preset_mode",
        "preset_modes",
        "humidity",
        "current_humidity",
        "fan_mode",
    ],
    "cover": ["current_position", "current_tilt_position"],
    "fan": ["percentage", "preset_mode", "direction", "oscillating"],
    "media_player": [
        "volume_level",
        "is_volume_muted",
        "media_content_type",
        "media_title",
        "media_artist",
        "source",
        "source_list",
    ],
    "vacuum": ["battery_level", "fan_speed"],
    "lock": [],
    "sensor": ["unit_of_measurement", "device_class", "state_class"],
    "binary_sensor": ["device_class"],
    "weather": [
        "temperature",
        "humidity",
        "pressure",
        "wind_speed",
        "wind_bearing",
        "forecast",
    ],
    "person": ["source"],
    "device_tracker": ["source_type", "battery_level"],
    "alarm_control_panel": ["code_arm_required", "changed_by"],
    "camera": ["is_streaming", "is_recording"],
    "humidifier": ["humidity", "mode", "available_modes"],
    "water_heater": ["temperature", "current_temperature", "operation_mode"],
    "scene": [],
    "script": [],
    "automation": ["last_triggered"],
    "input_boolean": [],
    "input_number": ["min", "max", "step", "mode"],
    "input_select": ["options"],
    "input_text": ["min", "max", "pattern", "mode"],
    "timer": ["duration", "remaining"],
    "counter": [],
    "number": ["min", "max", "step", "mode", "unit_of_measurement"],
    "select": ["options"],
    "button": [],
    "text": ["min", "max", "pattern", "mode"],
}

# Human-readable state translations
STATE_TRANSLATIONS: dict[str, dict[str, str]] = {
    "light": {"on": "ACCESA", "off": "SPENTA", "unavailable": "NON DISPONIBILE"},
    "switch": {"on": "ACCESO", "off": "SPENTO", "unavailable": "NON DISPONIBILE"},
    "cover": {
        "open": "APERTA",
        "closed": "CHIUSA",
        "opening": "IN APERTURA",
        "closing": "IN CHIUSURA",
        "unavailable": "NON DISPONIBILE",
    },
    "lock": {
        "locked": "CHIUSA",
        "unlocked": "APERTA",
        "locking": "IN CHIUSURA",
        "unlocking": "IN APERTURA",
        "unavailable": "NON DISPONIBILE",
    },
    "climate": {
        "off": "SPENTO",
        "heat": "RISCALDAMENTO",
        "cool": "RAFFREDDAMENTO",
        "heat_cool": "AUTO",
        "auto": "AUTOMATICO",
        "dry": "DEUMIDIFICAZIONE",
        "fan_only": "SOLO VENTILAZIONE",
        "unavailable": "NON DISPONIBILE",
    },
    "binary_sensor": {
        "on": "ATTIVO",
        "off": "INATTIVO",
        "unavailable": "NON DISPONIBILE",
    },
    "person": {"home": "A CASA", "not_home": "FUORI CASA", "unavailable": "SCONOSCIUTO"},
    "alarm_control_panel": {
        "disarmed": "DISARMATO",
        "armed_home": "ARMATO CASA",
        "armed_away": "ARMATO FUORI",
        "armed_night": "ARMATO NOTTE",
        "pending": "IN ATTESA",
        "triggered": "ATTIVATO",
        "unavailable": "NON DISPONIBILE",
    },
}

# Domains to skip (usually not useful for voice control)
SKIP_DOMAINS: set[str] = {
    "persistent_notification",
    "update",
    "tts",
    "stt",
    "conversation",
    "zone",
    "sun",
    "calendar",
}


def _translate_state(domain: str, state: str) -> str:
    """Translate state to human-readable format."""
    if domain in STATE_TRANSLATIONS:
        return STATE_TRANSLATIONS[domain].get(state, state.upper())
    if state == "on":
        return "ACCESO"
    if state == "off":
        return "SPENTO"
    if state == "unavailable":
        return "NON DISPONIBILE"
    if state == "unknown":
        return "SCONOSCIUTO"
    return state.upper()


def _format_attributes(domain: str, state: State) -> str:
    """Format relevant attributes for a domain."""
    relevant_keys = DOMAIN_RELEVANT_ATTRS.get(domain, [])
    if not relevant_keys:
        return ""

    attrs = []
    for key in relevant_keys:
        if key in state.attributes:
            value = state.attributes[key]
            if value is None:
                continue

            # Format specific attributes
            if key == "brightness":
                # Convert 0-255 to percentage
                pct = round((value / 255) * 100)
                attrs.append(f"luminosità: {pct}%")
            elif key == "color_temp":
                attrs.append(f"temperatura colore: {value}K")
            elif key == "volume_level":
                pct = round(value * 100)
                attrs.append(f"volume: {pct}%")
            elif key == "temperature" or key == "current_temperature":
                unit = state.attributes.get("unit_of_measurement", "°C")
                attrs.append(f"temperatura: {value}{unit}")
            elif key == "humidity" or key == "current_humidity":
                attrs.append(f"umidità: {value}%")
            elif key == "current_position":
                attrs.append(f"posizione: {value}%")
            elif key == "battery_level":
                attrs.append(f"batteria: {value}%")
            elif key == "percentage":
                attrs.append(f"velocità: {value}%")
            elif key == "unit_of_measurement" and domain == "sensor":
                # Skip, will be used with state
                continue
            elif isinstance(value, list):
                attrs.append(f"{key}: {', '.join(str(v) for v in value[:5])}")
            elif isinstance(value, bool):
                attrs.append(f"{key}: {'sì' if value else 'no'}")
            else:
                attrs.append(f"{key}: {value}")

    return ", ".join(attrs) if attrs else ""


class DeviceContextBuilder:
    """Build optimized device context for LLM."""

    def __init__(self, hass: HomeAssistant):
        """Initialize the device context builder."""
        self.hass = hass

    async def build_context(
        self,
        area_filter: list[str] | None = None,
        domain_filter: list[str] | None = None,
        include_unavailable: bool = False,
    ) -> str:
        """Build device context string grouped by area.

        Args:
            area_filter: List of area IDs to include. None = all areas.
            domain_filter: List of domains to include. None = all domains.
            include_unavailable: Whether to include unavailable entities.

        Returns:
            Formatted string with devices grouped by area.
        """
        area_reg = ar.async_get(self.hass)
        entity_reg = er.async_get(self.hass)
        device_reg = dr.async_get(self.hass)

        # Build area mapping
        areas: dict[str, str] = {
            area.id: area.name for area in area_reg.async_list_areas()
        }

        # Build entity to area mapping
        entity_to_area: dict[str, str | None] = {}
        for entity in entity_reg.entities.values():
            area_id = entity.area_id
            if not area_id and entity.device_id:
                device = device_reg.async_get(entity.device_id)
                if device:
                    area_id = device.area_id
            entity_to_area[entity.entity_id] = area_id

        # Group entities by area
        devices_by_area: dict[str, list[dict[str, Any]]] = {}
        no_area_devices: list[dict[str, Any]] = []

        for state in self.hass.states.async_all():
            entity_id = state.entity_id
            domain = entity_id.split(".")[0]

            # Skip unwanted domains
            if domain in SKIP_DOMAINS:
                continue

            # Apply domain filter
            if domain_filter and domain not in domain_filter:
                continue

            # Skip unavailable if not requested
            if not include_unavailable and state.state in ("unavailable", "unknown"):
                continue

            # Get area
            area_id = entity_to_area.get(entity_id)

            # Apply area filter
            if area_filter and area_id not in area_filter:
                continue

            # Build device info
            friendly_name = state.attributes.get("friendly_name", entity_id)
            translated_state = _translate_state(domain, state.state)

            # For sensors, append unit
            if domain == "sensor" and "unit_of_measurement" in state.attributes:
                translated_state = f"{state.state} {state.attributes['unit_of_measurement']}"

            attrs = _format_attributes(domain, state)

            device_info = {
                "entity_id": entity_id,
                "name": friendly_name,
                "domain": domain,
                "state": translated_state,
                "attributes": attrs,
            }

            if area_id and area_id in areas:
                area_name = areas[area_id]
                if area_name not in devices_by_area:
                    devices_by_area[area_name] = []
                devices_by_area[area_name].append(device_info)
            else:
                no_area_devices.append(device_info)

        # Build output string
        output_parts = []

        # Sorted areas
        for area_name in sorted(devices_by_area.keys()):
            devices = devices_by_area[area_name]
            output_parts.append(f"\n## {area_name}")

            # Group by domain within area
            by_domain: dict[str, list[dict[str, Any]]] = {}
            for device in devices:
                d = device["domain"]
                if d not in by_domain:
                    by_domain[d] = []
                by_domain[d].append(device)

            for domain in sorted(by_domain.keys()):
                for device in sorted(by_domain[domain], key=lambda x: x["name"]):
                    line = f"- {device['name']} ({device['entity_id']}): {device['state']}"
                    if device["attributes"]:
                        line += f" [{device['attributes']}]"
                    output_parts.append(line)

        # Devices without area
        if no_area_devices:
            output_parts.append("\n## Altro (senza area)")
            for device in sorted(no_area_devices, key=lambda x: x["name"]):
                line = f"- {device['name']} ({device['entity_id']}): {device['state']}"
                if device["attributes"]:
                    line += f" [{device['attributes']}]"
                output_parts.append(line)

        return "\n".join(output_parts)

    def get_available_areas(self) -> list[dict[str, str]]:
        """Get list of available areas."""
        area_reg = ar.async_get(self.hass)
        return [
            {"id": area.id, "name": area.name}
            for area in area_reg.async_list_areas()
        ]

    def get_available_domains(self) -> list[str]:
        """Get list of domains currently in use."""
        domains: set[str] = set()
        for state in self.hass.states.async_all():
            domain = state.entity_id.split(".")[0]
            if domain not in SKIP_DOMAINS:
                domains.add(domain)
        return sorted(domains)
