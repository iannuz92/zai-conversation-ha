"""Assistant memory for z.ai Conversation."""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

# Memory categories
CATEGORY_PREFERENCE = "preference"
CATEGORY_NOTE = "note"
CATEGORY_ROUTINE = "routine"
CATEGORY_CONTEXT = "context"


class AssistantMemory:
    """Manage persistent memory for the assistant."""

    def __init__(self, hass: HomeAssistant, entry_id: str):
        """Initialize the assistant memory.

        Args:
            hass: Home Assistant instance.
            entry_id: Config entry ID for this agent.
        """
        self.hass = hass
        self.entry_id = entry_id
        self._storage_path = Path(hass.config.path(".storage")) / f"zai_conversation.{entry_id}.json"
        self._data: dict[str, Any] = {
            "version": 1,
            "preferences": [],
            "notes": [],
            "routines": [],
            "context": {},
            "stats": {
                "total_interactions": 0,
                "last_interaction": None,
                "frequent_commands": {},
            },
        }
        self._loaded = False

    async def async_load(self) -> None:
        """Load memory from storage."""
        if self._loaded:
            return

        try:
            if self._storage_path.exists():
                data = await self.hass.async_add_executor_job(
                    self._read_file
                )
                if data:
                    self._data = data
                    _LOGGER.debug("Loaded memory for entry %s", self.entry_id)
        except Exception as err:
            _LOGGER.error("Error loading memory: %s", err)

        self._loaded = True

    def _read_file(self) -> dict[str, Any] | None:
        """Read memory file (runs in executor)."""
        try:
            with open(self._storage_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            return None

    async def async_save(self) -> None:
        """Save memory to storage."""
        try:
            await self.hass.async_add_executor_job(self._write_file)
            _LOGGER.debug("Saved memory for entry %s", self.entry_id)
        except Exception as err:
            _LOGGER.error("Error saving memory: %s", err)

    def _write_file(self) -> None:
        """Write memory file (runs in executor)."""
        self._storage_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self._storage_path, "w", encoding="utf-8") as f:
            json.dump(self._data, f, indent=2, ensure_ascii=False)

    # =========================================================================
    # Preferences
    # =========================================================================

    async def add_preference(self, preference: str, category: str = "general") -> None:
        """Add a user preference.

        Examples:
            - "Preferisco luci calde la sera"
            - "Non mi piace la musica alta"
            - "Svegliami sempre alle 7"
        """
        await self.async_load()

        entry = {
            "text": preference,
            "category": category,
            "added": dt_util.utcnow().isoformat(),
        }

        # Avoid duplicates
        existing = [p["text"].lower() for p in self._data["preferences"]]
        if preference.lower() not in existing:
            self._data["preferences"].append(entry)
            await self.async_save()
            _LOGGER.info("Added preference: %s", preference)

    async def remove_preference(self, preference_text: str) -> bool:
        """Remove a preference by text (partial match)."""
        await self.async_load()

        initial_len = len(self._data["preferences"])
        self._data["preferences"] = [
            p for p in self._data["preferences"]
            if preference_text.lower() not in p["text"].lower()
        ]

        if len(self._data["preferences"]) < initial_len:
            await self.async_save()
            return True
        return False

    def get_preferences(self) -> list[dict[str, Any]]:
        """Get all preferences."""
        return self._data.get("preferences", [])

    # =========================================================================
    # Notes
    # =========================================================================

    async def add_note(self, note: str, tags: list[str] | None = None) -> None:
        """Add a note.

        Examples:
            - "Ricordami che domani viene l'idraulico"
            - "Il codice dell'allarme è 1234"
        """
        await self.async_load()

        entry = {
            "text": note,
            "tags": tags or [],
            "added": dt_util.utcnow().isoformat(),
        }

        self._data["notes"].append(entry)
        await self.async_save()
        _LOGGER.info("Added note: %s", note)

    async def remove_note(self, note_text: str) -> bool:
        """Remove a note by text (partial match)."""
        await self.async_load()

        initial_len = len(self._data["notes"])
        self._data["notes"] = [
            n for n in self._data["notes"]
            if note_text.lower() not in n["text"].lower()
        ]

        if len(self._data["notes"]) < initial_len:
            await self.async_save()
            return True
        return False

    def get_notes(self) -> list[dict[str, Any]]:
        """Get all notes."""
        return self._data.get("notes", [])

    # =========================================================================
    # Context / User Info
    # =========================================================================

    async def set_context(self, key: str, value: Any) -> None:
        """Set a context value.

        Examples:
            - set_context("user_name", "Simone")
            - set_context("wake_time", "07:00")
        """
        await self.async_load()
        self._data["context"][key] = {
            "value": value,
            "updated": dt_util.utcnow().isoformat(),
        }
        await self.async_save()

    def get_context(self, key: str, default: Any = None) -> Any:
        """Get a context value."""
        ctx = self._data.get("context", {}).get(key)
        return ctx["value"] if ctx else default

    def get_all_context(self) -> dict[str, Any]:
        """Get all context values."""
        return {k: v["value"] for k, v in self._data.get("context", {}).items()}

    # =========================================================================
    # Stats & Tracking
    # =========================================================================

    async def record_interaction(self, command: str | None = None) -> None:
        """Record an interaction for stats."""
        await self.async_load()

        self._data["stats"]["total_interactions"] += 1
        self._data["stats"]["last_interaction"] = dt_util.utcnow().isoformat()

        if command:
            cmd_lower = command.lower()
            freq = self._data["stats"]["frequent_commands"]
            freq[cmd_lower] = freq.get(cmd_lower, 0) + 1

            # Keep only top 20 commands
            if len(freq) > 20:
                sorted_cmds = sorted(freq.items(), key=lambda x: x[1], reverse=True)
                self._data["stats"]["frequent_commands"] = dict(sorted_cmds[:20])

        await self.async_save()

    def get_stats(self) -> dict[str, Any]:
        """Get usage statistics."""
        return self._data.get("stats", {})

    # =========================================================================
    # Build Context for LLM
    # =========================================================================

    def build_memory_prompt(self) -> str:
        """Build memory context string for LLM prompt.

        Returns:
            Formatted string with user preferences, notes, and context.
        """
        parts = []

        # User context
        context = self.get_all_context()
        if context:
            parts.append("### Informazioni Utente")
            for key, value in context.items():
                # Make key human-readable
                readable_key = key.replace("_", " ").title()
                parts.append(f"- {readable_key}: {value}")

        # Preferences
        preferences = self.get_preferences()
        if preferences:
            parts.append("\n### Preferenze Utente")
            for pref in preferences[-10:]:  # Last 10 preferences
                parts.append(f"- {pref['text']}")

        # Notes
        notes = self.get_notes()
        if notes:
            parts.append("\n### Note da Ricordare")
            for note in notes[-5:]:  # Last 5 notes
                parts.append(f"- {note['text']}")

        # Stats summary
        stats = self.get_stats()
        if stats.get("total_interactions", 0) > 0:
            parts.append(f"\n### Statistiche")
            parts.append(f"- Interazioni totali: {stats['total_interactions']}")
            if stats.get("last_interaction"):
                try:
                    last = datetime.fromisoformat(stats["last_interaction"])
                    parts.append(f"- Ultima interazione: {last.strftime('%d/%m/%Y %H:%M')}")
                except ValueError:
                    pass

        return "\n".join(parts) if parts else ""

    # =========================================================================
    # Cleanup
    # =========================================================================

    async def async_clear(self) -> None:
        """Clear all memory."""
        self._data = {
            "version": 1,
            "preferences": [],
            "notes": [],
            "routines": [],
            "context": {},
            "stats": {
                "total_interactions": 0,
                "last_interaction": None,
                "frequent_commands": {},
            },
        }
        await self.async_save()
        _LOGGER.info("Cleared memory for entry %s", self.entry_id)

    async def async_delete_storage(self) -> None:
        """Delete storage file."""
        try:
            if self._storage_path.exists():
                await self.hass.async_add_executor_job(self._storage_path.unlink)
                _LOGGER.info("Deleted memory storage for entry %s", self.entry_id)
        except Exception as err:
            _LOGGER.error("Error deleting memory storage: %s", err)
