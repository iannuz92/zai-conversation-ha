# z.ai Conversation for Home Assistant

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/custom-components/hacs)
[![GitHub release](https://img.shields.io/github/v/release/iannuz92/zai-conversation-ha)](https://github.com/iannuz92/zai-conversation-ha/releases)

A custom Home Assistant integration that turns z.ai's GLM-4.7 model into a full **personal home assistant**. Based on the official Anthropic integration pattern, with native function calling support, configurable personality, persistent memory, and automatic device context.

## Features

### Core
- **GLM-4.7** — z.ai conversational model
- **Device control** — Voice and text commands with native HA function calling
- **Conversation Agent** — Full integration with Home Assistant's Assist system

### Personal Assistant
- **Persistent memory** — Remembers your preferences, notes, and context across sessions
- **Configurable personality** — Choose between Formal, Friendly, or Concise
- **Device context** — The LLM automatically receives the real state of lights, sensors, thermostats, and covers grouped by area
- **Area filter** — Limit context to only the areas you care about
- **Custom prompt** — Extra instructions to customize the assistant's behavior

## Installation

### HACS (Recommended)

1. Open **HACS** in Home Assistant
2. Go to **Integrations**
3. Click the three dots in the top right corner and select **Custom repositories**
4. Add: `https://github.com/iannuz92/zai-conversation-ha`
5. Category: **Integration**
6. Click **Add**
7. Search for "z.ai Conversation" and install it
8. **Restart Home Assistant**

### Manual Installation

1. Copy the `custom_components/zai_conversation` folder to your Home Assistant `custom_components` directory
2. Restart Home Assistant

## Configuration

### Getting Your API Key

1. Go to [z.ai](https://z.ai) and create an account
2. Navigate to API settings
3. Generate a new API key

### Setting Up the Integration

1. **Settings** > **Devices & Services** > **+ Add Integration**
2. Search for **"z.ai Conversation"**
3. Enter:
   - **API Key**: your z.ai API key
   - **Base URL**: `https://api.z.ai/api/anthropic` (default)
4. Click **Submit** — a connection test will be performed

### Configuration Options

After installation, click **Configure** on the integration:

#### Basic Options

| Option | Description | Default |
|--------|-------------|---------|
| **Personality** | Response style (Formal / Friendly / Concise) | Friendly |
| **Memory** | Enable persistent memory across sessions | Enabled |
| **Optimized prompt** | Use advanced prompt with device context | Enabled |
| **Extra instructions** | Additional template to customize behavior | — |
| **Control HA** | API for device control (`assist` / `intent` / `none`) | `assist` |
| **Recommended settings** | Use optimized parameters for the model | Enabled |

#### Advanced Options (disable "Recommended settings")

| Option | Description | Default | Range |
|--------|-------------|---------|-------|
| **Model** | Model to use | glm-4.7 | — |
| **Max tokens** | Maximum response length | 3000 | 1–8000 |
| **Temperature** | Response creativity | 0.7 | 0–1 |
| **Area filter** | Limit context to devices in specific areas | All | Multi-select |

## Usage

### Natural Commands

With "Control Home Assistant" set to `assist`:

```
"Turn on the living room lights"
"Set the thermostat to 22 degrees"
"What's the temperature in the bedroom?"
"Close all the blinds"
"Set the kitchen light to 50%"
"Turn off everything in the bedroom"
```

### Assistant Memory

The assistant remembers your preferences across sessions:

```
"Remember that I prefer warm lights in the evening"
"My ideal temperature is 21 degrees"
"Note that I need to call the plumber tomorrow"
```

### Personalities

| Personality | Style |
|-------------|-------|
| **Formal** | Professional, precise, polite |
| **Friendly** | Casual, warm, conversational |
| **Concise** | Minimal responses, just the essentials |

## Architecture

```
custom_components/zai_conversation/
├── __init__.py            # Entry point, client and memory setup
├── conversation.py        # Main entity, chat and API handling
├── config_flow.py         # Configuration flow UI
├── const.py               # Constants and defaults
├── entity.py              # Base entity
├── device_manager.py      # Device context builder by area
├── assistant_memory.py    # JSON persistent memory
├── prompt_templates.py    # Personality templates and instructions
├── manifest.json
├── strings.json
└── translations/
    └── en.json
```

### How It Works

1. **`conversation.py`** receives the user message via Assist
2. **`device_manager.py`** collects the state of all devices grouped by area
3. **`prompt_templates.py`** builds the system prompt with personality + device context + memory
4. **`assistant_memory.py`** injects stored preferences and notes
5. The complete prompt is sent along with Home Assistant instructions (tool calling) to the z.ai API
6. The response is processed: if it contains tool calls, they are executed and the result is sent back to the model for up to 10 iterations

## Troubleshooting

### "Cannot connect" error
- Verify your API key is correct
- Check your internet connection
- Verify the Base URL
- Check HA logs: **Settings** > **System** > **Logs**

### "Authentication error"
- Your API key may be expired
- Generate a new key from z.ai
- Reconfigure the integration

### Agent not responding
- Check HA logs for detailed errors
- Verify the conversation agent is enabled in Assist
- Try reducing max tokens
- Verify the z.ai service is operational

### Device control not working
- Make sure "Control Home Assistant" is set to `assist`
- Verify your devices are properly configured in HA
- Check logs for permission issues
- Try disabling the area filter to include all devices

### Assistant not remembering preferences
- Verify memory is enabled in the options
- Memory is stored in `/.storage/zai_memory_<entry_id>.json`
- Restart HA if memory fails to load

## Requirements

- **Home Assistant** 2024.1.0 or later
- **Python** 3.12+ (provided by the HA installation)
- **Package** `anthropic` v0.40.0 (installed automatically)
- **Account** on [z.ai](https://z.ai) with an active API key

## Support

- [Open an issue](https://github.com/iannuz92/zai-conversation-ha/issues) for bugs or feature requests
- Include Home Assistant logs when reporting issues
- Pull requests are welcome

## Credits

Based on the official [Anthropic integration](https://github.com/home-assistant/core/tree/dev/homeassistant/components/anthropic) from Home Assistant core, adapted for the z.ai API with advanced personal assistant features.

## License

MIT License — See the [LICENSE](LICENSE) file for details.

---

## Changelog

### v1.0.2

- Critical fix: access system prompt via `chat_log.content[0]` (SystemContent)
- Fix: API messages now correctly exclude SystemContent (`content[1:]`)
- Fix: tool_call attribute handling compatible with `llm.ToolInput`
- Fix: added `ConverseError` handling on `async_provide_llm_data`
- Fix: removed incompatible `ZaiBaseLLMEntity` inheritance
- Fix: removed `isinstance()` with TypeAliasType (crash on Python 3.12+)
- Cleaned up unused imports across all modules

### v1.0.1

- Fix indentation errors in `config_flow.py` and `conversation.py`
- Robust error handling with fallbacks

### v1.0.0

- Initial release
- GLM-4.7 model support via z.ai
- Conversation agent with function calling
- Persistent assistant memory
- Configurable personalities (Formal / Friendly / Concise)
- Automatic device context by area
- Full UI configuration
- HACS compatibility
