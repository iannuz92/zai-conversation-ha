"""Constants for the z.ai Conversation integration."""

from __future__ import annotations

from typing import Final

DOMAIN: Final = "zai_conversation"

DEFAULT_CONVERSATION_NAME: Final = "z.ai Conversation"

# Configuration
CONF_BASE_URL: Final = "base_url"
CONF_CHAT_MODEL: Final = "chat_model"
CONF_MAX_TOKENS: Final = "max_tokens"
CONF_TEMPERATURE: Final = "temperature"
CONF_PROMPT: Final = "prompt"
CONF_LLM_HASS_API: Final = "llm_hass_api"
CONF_RECOMMENDED: Final = "recommended"

# New configuration options
CONF_PERSONALITY: Final = "personality"
CONF_MEMORY_ENABLED: Final = "memory_enabled"
CONF_AREA_FILTER: Final = "area_filter"
CONF_USE_CUSTOM_PROMPT: Final = "use_custom_prompt"

# Personality options
PERSONALITY_FORMAL: Final = "formal"
PERSONALITY_FRIENDLY: Final = "friendly"
PERSONALITY_CONCISE: Final = "concise"

PERSONALITY_OPTIONS: Final = [
    PERSONALITY_FORMAL,
    PERSONALITY_FRIENDLY,
    PERSONALITY_CONCISE,
]

# Default values
DEFAULT_BASE_URL: Final = "https://api.z.ai/api/anthropic"

DEFAULT: Final = {
    CONF_CHAT_MODEL: "glm-4.7",
    CONF_MAX_TOKENS: 3000,
    CONF_TEMPERATURE: 0.7,  # Lowered from 1.0 for more consistent device control
    CONF_RECOMMENDED: True,
    CONF_PERSONALITY: PERSONALITY_FRIENDLY,
    CONF_MEMORY_ENABLED: True,
    CONF_AREA_FILTER: [],  # Empty = all areas
    CONF_USE_CUSTOM_PROMPT: True,  # Use our optimized prompt by default
}

# Available GLM-4 models
MODELS: Final = [
    "glm-4.7",
    "glm-4-flash",
    "glm-4-plus",
    "glm-4-air",
    "glm-4-airx",
    "glm-4-long",
]

# Subentry types
SUBENTRY_CONVERSATION: Final = "conversation"

# Memory storage key
MEMORY_KEY: Final = "memory"
