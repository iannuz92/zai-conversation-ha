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

# Default values
DEFAULT_BASE_URL: Final = "https://api.z.ai/api/anthropic"

DEFAULT: Final = {
    CONF_CHAT_MODEL: "glm-4-flash",
    CONF_MAX_TOKENS: 3000,
    CONF_TEMPERATURE: 1.0,
    CONF_RECOMMENDED: True,
}

# Available GLM-4 models
MODELS: Final = [
    "glm-4-flash",
    "glm-4-plus",
    "glm-4-air",
    "glm-4-airx",
    "glm-4-long",
]

# Subentry types
SUBENTRY_CONVERSATION: Final = "conversation"
