"""Conversation entity for z.ai integration."""

from __future__ import annotations

from collections.abc import Iterable
import logging
import re
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
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import llm
from homeassistant.helpers.entity_platform import AddEntitiesCallback

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
)
from .device_manager import DeviceContextBuilder
from .prompt_templates import build_system_prompt

_LOGGER = logging.getLogger(__name__)

MAX_TOOL_ITERATIONS = 10


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up conversation entities."""
    # Get or create memory instance
    memory = None
    if hass.data.get(DOMAIN) and hass.data[DOMAIN].get(config_entry.entry_id):
        memory = hass.data[DOMAIN][config_entry.entry_id].get(MEMORY_KEY)

    async_add_entities([ZaiConversationEntity(config_entry, hass, memory)])


def _format_tool(
    tool: llm.Tool, custom_serializer: Any | None = None
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
    """Transform HA chat_log content into z.ai/Anthropic API format.

    NOTE: SystemContent is skipped here - it is handled separately
    via the 'system' parameter of the API call.
    """
    messages: list[MessageParam] = []

    for content in chat_content:
        # Skip SystemContent - handled separately
        if isinstance(content, conversation.SystemContent):
            continue

        if isinstance(content, conversation.UserContent):
            # Combine consecutive user messages
            if not messages or messages[-1]["role"] != "user":
                messages.append(
                    MessageParam(
                        role="user",
                        content=content.content or "",
                    )
                )
            elif isinstance(messages[-1]["content"], str):
                messages[-1]["content"] = [
                    TextBlockParam(type="text", text=messages[-1]["content"]),
                    TextBlockParam(type="text", text=content.content or ""),
                ]
            else:
                messages[-1]["content"].append(
                    TextBlockParam(type="text", text=content.content or "")
                )

        elif isinstance(content, conversation.AssistantContent):
            # Combine consecutive assistant messages
            if not messages or messages[-1]["role"] != "assistant":
                messages.append(
                    MessageParam(
                        role="assistant",
                        content=[],
                    )
                )

            if content.content:
                messages[-1]["content"].append(
                    TextBlockParam(type="text", text=content.content)
                )

            # Add tool uses
            if content.tool_calls:
                for tool_call in content.tool_calls:
                    tool_name = getattr(tool_call, "tool_name", None) or getattr(tool_call, "name", "unknown")
                    tool_args = getattr(tool_call, "tool_args", None) or getattr(tool_call, "args", {})
                    tool_id = getattr(tool_call, "id", "unknown")
                    messages[-1]["content"].append(
                        {
                            "type": "tool_use",
                            "id": tool_id,
                            "name": tool_name,
                            "input": tool_args,
                        }
                    )

        elif isinstance(content, conversation.ToolResultContent):
            # Tool result - group with existing user message or create new one
            tool_result_block = {
                "type": "tool_result",
                "tool_use_id": content.tool_call_id,
                "content": content.tool_result if content.tool_result else "",
                "is_error": False,
            }

            if not messages or messages[-1]["role"] != "user":
                messages.append(
                    MessageParam(
                        role="user",
                        content=[tool_result_block],
                    )
                )
            elif isinstance(messages[-1]["content"], str):
                messages[-1]["content"] = [
                    TextBlockParam(type="text", text=messages[-1]["content"]),
                    tool_result_block,
                ]
            else:
                messages[-1]["content"].append(tool_result_block)

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


# Patterns to detect memory-related user messages (Italian + English)
_MEMORY_PREFERENCE_PATTERNS = re.compile(
    r"(?:ricorda(?:ti)?|remember|nota(?:ti)?|note|salva|save|annota|preferisco|i prefer|mi piace|i like|"
    r"non mi piace|i don'?t like|la mia .+ (?:preferit[ao]|ideale|favorit[ae])|my (?:favorite|preferred|ideal))",
    re.IGNORECASE,
)

_MEMORY_NOTE_PATTERNS = re.compile(
    r"(?:ricordami|remind me|annotati|note to self|da ricordare|don'?t forget|non dimenticare|segna(?:ti)?)",
    re.IGNORECASE,
)


async def _extract_and_save_memory(
    memory: AssistantMemory,
    user_text: str,
) -> None:
    """Detect memory-related intents in user text and save to memory.

    This analyzes the user's message for preference/note patterns and
    automatically persists them to the assistant's memory.
    """
    text = user_text.strip()
    if len(text) < 5:
        return

    try:
        if _MEMORY_NOTE_PATTERNS.search(text):
            # It's a note/reminder - save the full text
            await memory.add_note(text)
            _LOGGER.debug("Saved note from user: %s", text[:80])
        elif _MEMORY_PREFERENCE_PATTERNS.search(text):
            # It's a preference - save the full text
            await memory.add_preference(text)
            _LOGGER.debug("Saved preference from user: %s", text[:80])
    except Exception:
        _LOGGER.debug("Failed to extract memory from user input", exc_info=True)


class ZaiConversationEntity(
    conversation.ConversationEntity,
    conversation.AbstractConversationAgent,
):
    """z.ai conversation agent."""

    _attr_supports_streaming = True
    _attr_has_entity_name = True
    _attr_name = "z.ai"

    def __init__(
        self,
        entry: ConfigEntry,
        hass: HomeAssistant,
        memory: AssistantMemory | None = None,
    ) -> None:
        """Initialize the conversation entity."""
        self.entry = entry
        self._attr_unique_id = entry.entry_id
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
        memory_enabled = options.get(CONF_MEMORY_ENABLED, DEFAULT[CONF_MEMORY_ENABLED])

        # Record interaction and extract memory from user input
        try:
            if self._memory and memory_enabled:
                await self._memory.record_interaction(user_input.text)
                await _extract_and_save_memory(self._memory, user_input.text)
        except Exception:
            _LOGGER.debug("Failed to process memory", exc_info=True)

        try:
            await chat_log.async_provide_llm_data(
                user_input.as_llm_context(DOMAIN),
                options.get(CONF_LLM_HASS_API),
                options.get(CONF_PROMPT),
                user_input.extra_system_prompt,
            )
        except conversation.ConverseError as err:
            return err.as_conversation_result()

        await self._async_handle_chat_log(chat_log)

        return conversation.async_get_result_from_chat_log(user_input, chat_log)

    async def _async_handle_chat_log(
        self,
        chat_log: conversation.ChatLog,
    ) -> None:
        """Process chat log with z.ai API."""
        client: anthropic.AsyncAnthropic = self.entry.runtime_data
        options = self.entry.options

        # Get model configuration (use .get() with defaults to handle
        # entries configured before advanced options were added)
        if options.get(CONF_RECOMMENDED, True):
            model = DEFAULT[CONF_CHAT_MODEL]
            max_tokens = DEFAULT[CONF_MAX_TOKENS]
            temperature = DEFAULT[CONF_TEMPERATURE]
        else:
            model = options.get(CONF_CHAT_MODEL, DEFAULT[CONF_CHAT_MODEL])
            max_tokens = options.get(CONF_MAX_TOKENS, DEFAULT[CONF_MAX_TOKENS])
            temperature = options.get(CONF_TEMPERATURE, DEFAULT[CONF_TEMPERATURE])

        # Extract system prompt from chat_log.content[0] (SystemContent)
        # After async_provide_llm_data, the first element is always SystemContent
        system_prompt: list[TextBlockParam] = []

        try:
            use_custom_prompt = options.get(CONF_USE_CUSTOM_PROMPT, DEFAULT[CONF_USE_CUSTOM_PROMPT])

            # Get the HA-generated system content from content[0]
            ha_system_text = ""
            if chat_log.content and isinstance(chat_log.content[0], conversation.SystemContent):
                ha_system_text = chat_log.content[0].content or ""

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
                try:
                    if self._memory and options.get(CONF_MEMORY_ENABLED, DEFAULT[CONF_MEMORY_ENABLED]):
                        await self._memory.async_load()
                        memory_context = self._memory.build_memory_prompt()
                except Exception:
                    _LOGGER.debug("Failed to build memory context", exc_info=True)

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
                system_prompt = [
                    TextBlockParam(
                        type="text",
                        text=custom_prompt,
                        cache_control={"type": "ephemeral"},
                    )
                ]

                # Also include HA-generated system content (tool instructions etc.)
                if ha_system_text:
                    system_prompt.append(
                        TextBlockParam(
                            type="text",
                            text=ha_system_text,
                            cache_control={"type": "ephemeral"},
                        )
                    )
            else:
                # Use default HA system prompt only
                if ha_system_text:
                    system_prompt = [
                        TextBlockParam(
                            type="text",
                            text=ha_system_text,
                            cache_control={"type": "ephemeral"},
                        )
                    ]
        except Exception:
            _LOGGER.warning("Failed to build custom system prompt, using fallback", exc_info=True)
            system_prompt = []
            try:
                if chat_log.content and isinstance(chat_log.content[0], conversation.SystemContent):
                    fallback_text = chat_log.content[0].content or ""
                    if fallback_text:
                        system_prompt = [
                            TextBlockParam(
                                type="text",
                                text=fallback_text,
                                cache_control={"type": "ephemeral"},
                            )
                        ]
            except Exception:
                _LOGGER.warning("Failed to get any system prompt", exc_info=True)

        # Format messages - skip SystemContent (index 0)
        messages = _convert_content(chat_log.content[1:])

        # Ensure we have at least one message
        if not messages:
            messages = [MessageParam(role="user", content="Hello")]

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

        # Tool call iteration loop
        for _iteration in range(MAX_TOOL_ITERATIONS):
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
            messages = _convert_content(chat_log.content[1:])
            model_args["messages"] = messages
