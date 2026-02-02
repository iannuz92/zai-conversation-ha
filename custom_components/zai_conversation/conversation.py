"""Conversation entity for z.ai integration."""

from __future__ import annotations

from collections.abc import AsyncGenerator, Iterable
from dataclasses import dataclass, field
import json
import logging
from typing import Any, Literal

import anthropic
from anthropic.types import (
    MessageParam,
    MessageStreamEvent,
    RawContentBlockDeltaEvent,
    RawContentBlockStartEvent,
    RawMessageDeltaEvent,
    RawMessageStartEvent,
    TextBlockParam,
    ToolParam,
)
from anthropic.types.message_create_params import MessageCreateParamsStreaming
from anthropic.types.text_citation_param import TextCitationParam
import voluptuous_openapi

from homeassistant.components import conversation
from homeassistant.config_entries import ConfigEntry, ConfigSubentry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import ulid

from . import ZaiConfigEntry
from .const import (
    CONF_CHAT_MODEL,
    CONF_LLM_HASS_API,
    CONF_MAX_TOKENS,
    CONF_PROMPT,
    CONF_RECOMMENDED,
    CONF_TEMPERATURE,
    DEFAULT,
    DOMAIN,
    SUBENTRY_CONVERSATION,
)
from .entity import ZaiBaseLLMEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up conversation entities."""
    assert isinstance(config_entry, ZaiConfigEntry)

    async_add_entities([ZaiConversationEntity(config_entry)])


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
            # Tool results
            for tool_result in content.tool_results:
                messages.append(
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "tool_result",
                                "tool_use_id": tool_result.call_id,
                                "content": (
                                    tool_result.result if tool_result.result else ""
                                ),
                                "is_error": tool_result.error,
                            }
                        ],
                    }
                )

    return messages


@dataclass(slots=True)
class CitationDetails:
    """Citation tracking."""

    index: int = 0
    length: int = 0
    citations: list[TextCitationParam] = field(default_factory=list)


async def _transform_stream(
    chat_log: conversation.ChatLog,
    stream: anthropic.AsyncStream[MessageStreamEvent],
    output_tool: str | None = None,
) -> AsyncGenerator[conversation.Content, None]:
    """Transform z.ai stream to HA conversation format."""
    content_type: Literal["text", "tool_use"] | None = None
    content_text = ""
    tool_call_id: str | None = None
    tool_call_name: str | None = None
    tool_call_args = ""

    input_tokens = 0
    output_tokens = 0

    async for event in stream:
        if isinstance(event, RawMessageStartEvent):
            input_tokens = event.message.usage.input_tokens

        elif isinstance(event, RawContentBlockStartEvent):
            if event.content_block.type == "text":
                content_type = "text"
            elif event.content_block.type == "tool_use":
                content_type = "tool_use"
                tool_call_id = event.content_block.id
                tool_call_name = event.content_block.name

        elif isinstance(event, RawContentBlockDeltaEvent):
            if content_type == "text" and event.delta.type == "text_delta":
                content_text += event.delta.text
                yield conversation.AssistantStreamChunk(text=event.delta.text)

            elif content_type == "tool_use" and event.delta.type == "input_json_delta":
                tool_call_args += event.delta.partial_json

        elif isinstance(event, RawMessageDeltaEvent):
            output_tokens = event.usage.output_tokens

            # Finalize tool call if any
            if content_type == "tool_use" and tool_call_id and tool_call_name:
                try:
                    parsed_args = json.loads(tool_call_args)
                    chat_log.async_add_assistant_content(
                        conversation.AssistantContent(
                            tool_calls=[
                                conversation.ToolCall(
                                    id=tool_call_id,
                                    name=tool_call_name,
                                    args=parsed_args,
                                )
                            ]
                        )
                    )
                    yield conversation.AssistantToolCallChunk(
                        id=tool_call_id,
                        name=tool_call_name,
                        args=parsed_args,
                    )
                except json.JSONDecodeError:
                    _LOGGER.error("Failed to parse tool call args: %s", tool_call_args)

                # Reset for next tool call
                tool_call_id = None
                tool_call_name = None
                tool_call_args = ""

    # Add final text content if any
    if content_text:
        chat_log.async_add_assistant_content(
            conversation.AssistantContent(content=content_text)
        )

    # Add token usage
    if input_tokens or output_tokens:
        chat_log.async_add_trace_event(
            conversation.ConversationTraceEventType.LLM_TOOL_CALL,
            {
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "model": chat_log.model,
            },
        )


class ZaiConversationEntity(
    conversation.ConversationEntity,
    conversation.AbstractConversationAgent,
    ZaiBaseLLMEntity,
):
    """z.ai conversation agent."""

    _attr_supports_streaming = True

    def __init__(self, entry: ZaiConfigEntry) -> None:
        """Initialize the conversation entity."""
        super().__init__(entry, entry)
        self._attr_name = "z.ai"
        self._attr_unique_id = entry.entry_id

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

        await chat_log.async_provide_llm_data(
            user_input.as_llm_context(DOMAIN),
            options.get(CONF_LLM_HASS_API),
            options.get(CONF_PROMPT),
            user_input.extra_system_prompt,
        )

        await self._async_handle_chat_log(chat_log)

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

        # Format system prompt
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
        model_args = MessageCreateParamsStreaming(
            model=model,
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature,
            system=system_prompt,
            stream=True,
        )

        if tools:
            model_args["tools"] = tools

        chat_log.model = model

        # Tool call iteration
        max_iterations = 10
        for iteration in range(max_iterations):
            try:
                stream = await client.messages.create(**model_args)

                async for chunk in _transform_stream(chat_log, stream):
                    chat_log.async_stream_chunk(chunk)

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
