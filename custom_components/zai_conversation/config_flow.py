"""Config flow for z.ai Conversation integration."""

from __future__ import annotations

from functools import partial
import logging
from types import MappingProxyType
from typing import Any

import anthropic
import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    ConfigSubentry,
    OptionsFlow,
)
from homeassistant.const import CONF_API_KEY, CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers import area_registry as ar
from homeassistant.helpers.selector import (
    BooleanSelector,
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TemplateSelector,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .const import (
    CONF_AREA_FILTER,
    CONF_BASE_URL,
    CONF_CHAT_MODEL,
    CONF_LLM_HASS_API,
    CONF_MAX_TOKENS,
    CONF_MEMORY_ENABLED,
    CONF_PERSONALITY,
    CONF_PROMPT,
    CONF_RECOMMENDED,
    CONF_TEMPERATURE,
    CONF_USE_CUSTOM_PROMPT,
    DEFAULT,
    DEFAULT_BASE_URL,
    DEFAULT_CONVERSATION_NAME,
    DOMAIN,
    MODELS,
    PERSONALITY_CONCISE,
    PERSONALITY_FORMAL,
    PERSONALITY_FRIENDLY,
    PERSONALITY_OPTIONS,
    SUBENTRY_CONVERSATION,
)

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_API_KEY): TextSelector(
            TextSelectorConfig(type=TextSelectorType.PASSWORD)
        ),
        vol.Optional(CONF_BASE_URL, default=DEFAULT_BASE_URL): TextSelector(
            TextSelectorConfig(type=TextSelectorType.URL)
        ),
    }
)

RECOMMENDED_OPTIONS = {
    CONF_LLM_HASS_API: "assist",
    CONF_RECOMMENDED: True,
    CONF_PERSONALITY: DEFAULT[CONF_PERSONALITY],
    CONF_MEMORY_ENABLED: DEFAULT[CONF_MEMORY_ENABLED],
    CONF_USE_CUSTOM_PROMPT: DEFAULT[CONF_USE_CUSTOM_PROMPT],
}


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> None:
    """Validate the user input allows us to connect.

    Data has the keys from STEP_USER_DATA_SCHEMA with values provided by the user.
    """
    api_key = data[CONF_API_KEY]
    base_url = data.get(CONF_BASE_URL, DEFAULT_BASE_URL)

    client = await hass.async_add_executor_job(
        partial(
            anthropic.AsyncAnthropic,
            api_key=api_key,
            base_url=base_url,
        )
    )

    # Test the connection by making a simple API call
    try:
        await client.messages.create(
            model="glm-4.7",
            max_tokens=10,
            messages=[{"role": "user", "content": "test"}],
            timeout=10.0,
        )
    except anthropic.AuthenticationError as err:
        _LOGGER.error("Authentication error: %s", err)
        raise
    except anthropic.APITimeoutError as err:
        _LOGGER.error("Timeout error: %s", err)
        raise
    except anthropic.APIConnectionError as err:
        _LOGGER.error("Connection error: %s", err)
        raise
    except anthropic.AnthropicError as err:
        _LOGGER.error("z.ai API error: %s", err)
        raise


class ZaiConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for z.ai Conversation."""

    VERSION = 1

    @staticmethod
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        """Get the options flow for this handler."""
        return ZaiOptionsFlowHandler()

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                await validate_input(self.hass, user_input)
            except anthropic.APITimeoutError:
                errors["base"] = "timeout_connect"
            except anthropic.APIConnectionError:
                errors["base"] = "cannot_connect"
            except anthropic.AuthenticationError:
                errors["base"] = "authentication_error"
            except anthropic.AnthropicError:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                return self.async_create_entry(
                    title="z.ai",
                    data=user_input,
                    options=RECOMMENDED_OPTIONS,
                )

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
        )


class ZaiOptionsFlowHandler(OptionsFlow):
    """Handle options flow for z.ai Conversation."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle conversation agent configuration."""
        errors: dict[str, str] = {}

        if user_input is not None:
            if CONF_RECOMMENDED in user_input:
                recommended = user_input.pop(CONF_RECOMMENDED)
                if not recommended:
                    return await self.async_step_advanced()

            return self.async_create_entry(title="", data=user_input)

        schema_dict: dict[vol.Marker, Any] = {}
        options = self.config_entry.options or {}

        # Personality selector
        schema_dict[
            vol.Optional(
                CONF_PERSONALITY,
                default=options.get(CONF_PERSONALITY, DEFAULT[CONF_PERSONALITY]),
            )
        ] = SelectSelector(
            SelectSelectorConfig(
                mode=SelectSelectorMode.DROPDOWN,
                options=[
                    {"value": PERSONALITY_FORMAL, "label": "Formale"},
                    {"value": PERSONALITY_FRIENDLY, "label": "Amichevole"},
                    {"value": PERSONALITY_CONCISE, "label": "Conciso"},
                ],
                translation_key=CONF_PERSONALITY,
            )
        )

        # Memory toggle
        schema_dict[
            vol.Optional(
                CONF_MEMORY_ENABLED,
                default=options.get(CONF_MEMORY_ENABLED, DEFAULT[CONF_MEMORY_ENABLED]),
            )
        ] = BooleanSelector()

        # Use custom prompt toggle
        schema_dict[
            vol.Optional(
                CONF_USE_CUSTOM_PROMPT,
                default=options.get(CONF_USE_CUSTOM_PROMPT, DEFAULT[CONF_USE_CUSTOM_PROMPT]),
            )
        ] = BooleanSelector()

        # Custom prompt template (only shown if use_custom_prompt is True, but always available)
        schema_dict[vol.Optional(CONF_PROMPT, default=options.get(CONF_PROMPT, ""))] = (
            TemplateSelector()
        )

        # LLM API selector
        schema_dict[
            vol.Optional(
                CONF_LLM_HASS_API,
                default=options.get(CONF_LLM_HASS_API, "assist"),
            )
        ] = SelectSelector(
            SelectSelectorConfig(
                mode=SelectSelectorMode.DROPDOWN,
                options=["none", "assist", "intent"],
            )
        )

        schema_dict[
            vol.Optional(
                CONF_RECOMMENDED,
                default=options.get(CONF_RECOMMENDED, True),
            )
        ] = BooleanSelector()

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(schema_dict),
            errors=errors,
        )
            errors=errors,
        )

    async def async_step_advanced(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle advanced configuration."""
        errors: dict[str, str] = {}

        if user_input is not None:
            return self.async_create_entry(
                title="",
                data={CONF_RECOMMENDED: False, **user_input},
            )

        options = self.config_entry.options or {}

        # Get available areas for filter
        area_reg = ar.async_get(self.hass)
        area_options = [
            {"value": area.id, "label": area.name}
            for area in area_reg.async_list_areas()
        ]

        schema = vol.Schema(
            {
                vol.Required(
                    CONF_CHAT_MODEL,
                    default=options.get(CONF_CHAT_MODEL, DEFAULT[CONF_CHAT_MODEL]),
                ): (
                    SelectSelector(
                        SelectSelectorConfig(
                            mode=SelectSelectorMode.DROPDOWN,
                            options=MODELS,
                            custom_value=True,
                        )
                    )
                ),
                vol.Optional(
                    CONF_MAX_TOKENS,
                    default=options.get(CONF_MAX_TOKENS, DEFAULT[CONF_MAX_TOKENS]),
                ): (
                    NumberSelector(
                        NumberSelectorConfig(
                            min=1,
                            max=8000,
                            mode=NumberSelectorMode.BOX,
                        )
                    )
                ),
                vol.Optional(
                    CONF_TEMPERATURE,
                    default=options.get(CONF_TEMPERATURE, DEFAULT[CONF_TEMPERATURE]),
                ): (
                    NumberSelector(
                        NumberSelectorConfig(
                            min=0,
                            max=1,
                            step=0.05,
                            mode=NumberSelectorMode.SLIDER,
                        )
                    )
                ),
                vol.Optional(
                    CONF_AREA_FILTER,
                    default=options.get(CONF_AREA_FILTER, DEFAULT[CONF_AREA_FILTER]),
                ): (
                    SelectSelector(
                        SelectSelectorConfig(
                            mode=SelectSelectorMode.DROPDOWN,
                            options=area_options,
                            multiple=True,
                        )
                    )
                    if area_options
                    else SelectSelector(
                        SelectSelectorConfig(
                            mode=SelectSelectorMode.DROPDOWN,
                            options=[],
                            multiple=True,
                        )
                    )
                ),
            }
        )

        return self.async_show_form(
            step_id="advanced",
            data_schema=schema,
            errors=errors,
        )
