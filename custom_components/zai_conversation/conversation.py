"""Conversation entity for z.ai integration."""

from __future__ import annotations

from collections.abc import AsyncGenerator, Iterable
from dataclasses import dataclass, field
import json
import logging
from typing import Any, Literal

import anthropic
from anthropic.types import (
    Message,
    MessageParam,
    TextBlockParam,
    ToolParam,
)
import voluptuous_openapi

from homeassistant.components import conversation
from homeassistant.config_entries import ConfigEntry, ConfigSubentry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import llm
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import ulid

from . import ZaiConfigEntry
from .assistant_memory import AssistantMemory
from .const import (
    CONF_AREA_FILTER,
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
    DOMAIN,
    MEMORY_KEY,
    SUBENTRY_CONVERSATION,
)
from .device_manager import DeviceContextBuilder
from .entity import ZaiBaseLLMEntity
from .prompt_templates import PERSONALITY_FRIENDLY, build_system_prompt

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up conversation entities."""
    assert isinstance(config_entry, ZaiConfigEntry)

    # Get or create memory instance
    memory = None
    if hass.data.get(DOMAIN) and hass.data[DOMAIN].get(config_entry.entry_id):
        memory = hass.data[DOMAIN][config_entry.entry_id].get(MEMORY_KEY)

    async_add_entities([ZaiConversationEntity(config_entry, hass, memory)])


def _format_tool(
    tool: conversation.llm.Tool, custom_serializer: Any | None = None
) -> ToolParam:
    """Format tool for z.ai API."""
    return ToolParam(
        name=tool.name,
        description=tool.description or "",
        input_schema=voluptuous_openapi.convert(
            tool.parameters, custom_serializer=custom_serializer
        ),
    )


def _convert_content(
    chat_content: Iterable[conversation.Content],
) -> list[MessageParam]:
    """Transform HA chat_log content into z.ai/Anthropic API format."""
    messages: list[MessageParam] = []

    for content in chat_content:
        if isinstance(content, conversation.UserContent):
            # User message
            message_parts: list[Any] = []

            if content.content:
                message_parts.append({"type": "text", "text": content.content})

            # Add attachments
            if content.attachments:
                for attachment in content.attachments:
                    if attachment.content_type.startswith("image/"):
                        message_parts.append(
                            {
                                "type": "image",
                                "source": {
                                    "type": "base64",
                                    "media_type": attachment.content_type,
                                    "data": attachment.data,
                                },
                            }
                        )
                    elif attachment.content_type == "application/pdf":
                        message_parts.append(
                            {
                                "type": "document",
                                "source": {
                                    "type": "base64",
                                    "media_type": "application/pdf",
                                    "data": attachment.data,
                                },
                            }
                        )

            messages.append({"role": "user", "content": message_parts})

        elif isinstance(content, conversation.AssistantContent):
            # Assistant message
            message_parts = []

            if content.content:
                message_parts.append({"type": "text", "text": content.content})

            # Add tool uses
                if content.tool_calls:
                    for tool_call in content.tool_calls:
                        message_parts.append(
                            {
                                "type": "tool_use",
                                "id": tool_call.id,
                                "name": tool_call.name,
                                "input": tool_call.args,
                            }
                        )

            messages.append({"role": "assistant", "content": message_parts})

        elif isinstance(content, conversation.ToolResultContent):
            # Tool result
            messages.append(
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "tool_result",
                            "tool_use_id": content.tool_call_id,
                            "content": (
                                content.tool_result if content.tool_result else ""
                            ),
                            "is_error": False,
                        }
                    ],
                }
            )

    return messages


async def _process_message(
    chat_log: conversation.ChatLog,
    message: Message,
    agent_id: str,
) -> None:
    """Transform a z.ai message into HA conversation content."""
    content_text = ""
    assistant_added = False

    for block in message.content:
        if block.type == "text":
            content_text += block.text
        elif block.type == "tool_use":
            async for _ in chat_log.async_add_assistant_content(
                conversation.AssistantContent(
                    agent_id=agent_id,
                    tool_calls=[
                        llm.ToolInput(
                            tool_name=block.name,
                            tool_args=block.input,
                            id=block.id,
                        )
                    ],
                )
            ):
                pass
            assistant_added = True

    if content_text:
        chat_log.async_add_assistant_content_without_tools(
            conversation.AssistantContent(content=content_text, agent_id=agent_id)
        )
        assistant_added = True

    if not assistant_added:
        chat_log.async_add_assistant_content_without_tools(
            conversation.AssistantContent(
                content="Sorry, I couldn't get a response from the model.",
                agent_id=agent_id,
            )
        )


class ZaiConversationEntity(
    conversation.ConversationEntity,
    conversation.AbstractConversationAgent,
    ZaiBaseLLMEntity,
):
    """z.ai conversation agent."""

    _attr_supports_streaming = True

    def __init__(
        self,
        entry: ZaiConfigEntry,
        hass: HomeAssistant,
        memory: AssistantMemory | None = None,
    ) -> None:
        """Initialize the conversation entity."""
        super().__init__(entry, entry)
        self._attr_name = "z.ai"
        self._attr_unique_id = entry.entry_id
        self.entry = entry
        self._hass = hass
        self._memory = memory
        self._device_builder = DeviceContextBuilder(hass)

    @property
    def supported_languages(self) -> list[str] | Literal["*"]:
        """Return supported languages."""
        return "*"

    async def _async_handle_message(
        self,
        user_input: conversation.ConversationInput,
        chat_log: conversation.ChatLog,
    ) -> conversation.ConversationResult:
        """Handle a conversation message."""
        options = self.entry.options

        # Record interaction in memory
        if self._memory and options.get(CONF_MEMORY_ENABLED, DEFAULT[CONF_MEMORY_ENABLED]):
            await self._memory.record_interaction(user_input.text)

        await chat_log.async_provide_llm_data(
            user_input.as_llm_context(DOMAIN),
            options.get(CONF_LLM_HASS_API),
            options.get(CONF_PROMPT),
            user_input.extra_system_prompt,
        )

        await self._async_handle_chat_log(chat_log)

        if not chat_log.content or not isinstance(
            chat_log.content[-1], conversation.AssistantContent
        ):
            chat_log.async_add_assistant_content_without_tools(
                conversation.AssistantContent(
                    content="Sorry, I couldn't get a response from the model.",
                    agent_id=self.entity_id,
                )
            )

        return conversation.async_get_result_from_chat_log(user_input, chat_log)

    async def _async_handle_chat_log(
        self,
        chat_log: conversation.ChatLog,
    ) -> None:
        """Process chat log with z.ai API."""
        client: anthropic.AsyncAnthropic = self.entry.runtime_data
        options = self.entry.options

        # Get model configuration
        model = (
            options[CONF_CHAT_MODEL]
            if not options.get(CONF_RECOMMENDED)
            else DEFAULT[CONF_CHAT_MODEL]
        )
        max_tokens = (
            options[CONF_MAX_TOKENS]
            if not options.get(CONF_RECOMMENDED)
            else DEFAULT[CONF_MAX_TOKENS]
        )
        temperature = (
            options[CONF_TEMPERATURE]
            if not options.get(CONF_RECOMMENDED)
            else DEFAULT[CONF_TEMPERATURE]
        )

        # Build custom system prompt if enabled
        use_custom_prompt = options.get(CONF_USE_CUSTOM_PROMPT, DEFAULT[CONF_USE_CUSTOM_PROMPT])

        if use_custom_prompt:
            # Get personality
            personality = options.get(CONF_PERSONALITY, DEFAULT[CONF_PERSONALITY])

            # Build device context
            area_filter = options.get(CONF_AREA_FILTER, DEFAULT[CONF_AREA_FILTER])
            devices_context = await self._device_builder.build_context(
                area_filter=area_filter if area_filter else None,
            )

            # Build memory context
            memory_context = ""
            if self._memory and options.get(CONF_MEMORY_ENABLED, DEFAULT[CONF_MEMORY_ENABLED]):
                await self._memory.async_load()
                memory_context = self._memory.build_memory_prompt()

            # Get extra instructions from user prompt template
            extra_instructions = options.get(CONF_PROMPT, "")

            # Build the complete prompt
            custom_prompt = build_system_prompt(
                personality=personality,
                devices_context=devices_context,
                memory_context=memory_context,
                extra_instructions=extra_instructions,
            )

            # Create system prompt blocks with our custom prompt
            system_prompt: list[TextBlockParam] = [
                TextBlockParam(
                    type="text",
                    text=custom_prompt,
                    cache_control={"type": "ephemeral"},
                )
            ]

            # Also include any HA-generated system content (for tool instructions)
            for system in chat_log.system:
                # Skip if it looks like the default HA prompt (we're replacing it)
                if "assist" not in system.content.lower()[:100]:
                    system_prompt.append(
                        TextBlockParam(
                            type="text",
                            text=system.content,
                            cache_control={"type": "ephemeral"},
                        )
                    )
        else:
            # Use default HA system prompts
            system_prompt: list[TextBlockParam] = []
            for system in chat_log.system:
                system_prompt.append(
                    TextBlockParam(
                        type="text",
                        text=system.content,
                        cache_control={"type": "ephemeral"},
                    )
                )

        # Format messages
        messages = _convert_content(chat_log.content)

        # Format tools
        tools: list[ToolParam] = []
        if chat_log.llm_api:
            tools = [
                _format_tool(tool, chat_log.llm_api.custom_serializer)
                for tool in chat_log.llm_api.tools
            ]

        # Prepare API call parameters
        model_args: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }

        if system_prompt:
            model_args["system"] = system_prompt

        if tools:
            model_args["tools"] = tools

        chat_log.model = model

        # Tool call iteration
        max_iterations = 10
        iteration = 0
        for iteration in range(max_iterations):
            try:
                message = await client.messages.create(**model_args)

                await _process_message(chat_log, message, self.entity_id)

            except anthropic.AnthropicError as err:
                raise HomeAssistantError(
                    f"Sorry, I had a problem talking to z.ai: {err}"
                ) from err

            # Check if we need to continue with tool results
            if not chat_log.unresponded_tool_results:
                break

            # Add tool results and continue
            messages = _convert_content(chat_log.content)
            model_args["messages"] = messages

        if iteration == max_iterations - 1:
            _LOGGER.warning("Reached maximum tool call iterations")
