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
    ConfigSubentryFlowHandler,
)
from homeassistant.const import CONF_API_KEY, CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.selector import (
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
    CONF_BASE_URL,
    CONF_CHAT_MODEL,
    CONF_LLM_HASS_API,
    CONF_MAX_TOKENS,
    CONF_PROMPT,
    CONF_RECOMMENDED,
    CONF_TEMPERATURE,
    DEFAULT,
    DEFAULT_BASE_URL,
    DEFAULT_CONVERSATION_NAME,
    DOMAIN,
    MODELS,
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
            model="glm-4-flash",
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
    MINOR_VERSION = 1

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
                    subentries=[
                        ConfigSubentry(
                            type=SUBENTRY_CONVERSATION,
                            title=DEFAULT_CONVERSATION_NAME,
                            data=RECOMMENDED_OPTIONS,
                        ),
                    ],
                )

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
        )


class ConversationSubentryFlowHandler(ConfigSubentryFlowHandler, domain=DOMAIN):
    """Handle conversation subentry configuration."""

    type = SUBENTRY_CONVERSATION

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle conversation subentry initialization."""
        errors: dict[str, str] = {}

        if user_input is not None:
            if CONF_RECOMMENDED in user_input:
                recommended = user_input.pop(CONF_RECOMMENDED)
                if not recommended:
                    return await self.async_step_advanced()

            return self.async_create_subentry(
                title=user_input.pop(CONF_NAME, DEFAULT_CONVERSATION_NAME),
                data={**RECOMMENDED_OPTIONS, **user_input},
            )

        schema_dict: dict[vol.Marker, Any] = {}

        if self.subentry_id is None:
            schema_dict[vol.Required(CONF_NAME, default=DEFAULT_CONVERSATION_NAME)] = (
                TextSelector()
            )

        schema_dict[vol.Optional(CONF_PROMPT)] = TemplateSelector()
        schema_dict[vol.Optional(CONF_LLM_HASS_API)] = SelectSelector(
            SelectSelectorConfig(
                mode=SelectSelectorMode.DROPDOWN,
                options=["none", "assist", "intent"],
            )
        )

        if self.subentry_id is None:
            schema_dict[vol.Optional(CONF_RECOMMENDED, default=True)] = bool

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(schema_dict),
            errors=errors,
        )

    async def async_step_advanced(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle advanced configuration."""
        errors: dict[str, str] = {}

        if user_input is not None:
            return self.async_create_subentry(
                title=DEFAULT_CONVERSATION_NAME,
                data={CONF_RECOMMENDED: False, **user_input},
            )

        schema = vol.Schema(
            {
                vol.Required(CONF_CHAT_MODEL, default=DEFAULT[CONF_CHAT_MODEL]): (
                    SelectSelector(
                        SelectSelectorConfig(
                            mode=SelectSelectorMode.DROPDOWN,
                            options=MODELS,
                            custom_value=True,
                        )
                    )
                ),
                vol.Optional(CONF_MAX_TOKENS, default=DEFAULT[CONF_MAX_TOKENS]): (
                    NumberSelector(
                        NumberSelectorConfig(
                            min=1,
                            max=8000,
                            mode=NumberSelectorMode.BOX,
                        )
                    )
                ),
                vol.Optional(CONF_TEMPERATURE, default=DEFAULT[CONF_TEMPERATURE]): (
                    NumberSelector(
                        NumberSelectorConfig(
                            min=0,
                            max=1,
                            step=0.05,
                            mode=NumberSelectorMode.SLIDER,
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
