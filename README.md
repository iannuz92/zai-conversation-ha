# z.ai Conversation Integration for Home Assistant

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/custom-components/hacs)

A custom integration for Home Assistant that adds z.ai's GLM-4 models as conversation agents. This integration is based on the official Anthropic integration pattern and supports function calling for Home Assistant device control.

## Features

- 🤖 **GLM-4 Models Support**: Access to glm-4.7, glm-4-flash, glm-4-plus, glm-4-air, and more
- 💬 **Conversation Agent**: Full integration with Home Assistant's conversation system
- 🔧 **Function Calling**: Control Home Assistant devices through natural language
- ⚡ **Fast Responses**: Optimized for quick replies
- 🎛️ **Customizable**: Configure model, temperature, max tokens, and prompts
- 🔐 **Secure**: API key stored securely in Home Assistant

## Installation

### HACS (Recommended)

1. Open HACS in your Home Assistant instance
2. Click on "Integrations"
3. Click the three dots in the top right corner
4. Select "Custom repositories"
5. Add this repository URL: `https://github.com/iannuz92/zai-conversation-ha`
6. Select category: "Integration"
7. Click "Add"
8. Find "z.ai Conversation" in the integration list and install it
9. Restart Home Assistant

### Manual Installation

1. Copy the `custom_components/zai_conversation` folder to your Home Assistant's `custom_components` directory
2. Restart Home Assistant

## Configuration

### Getting Your z.ai API Key

1. Visit [z.ai](https://z.ai) and sign up for an account
2. Navigate to your API settings
3. Generate a new API key
4. Copy the API key (you'll need it during setup)

### Setting Up the Integration

1. Go to **Settings** → **Devices & Services**
2. Click **+ Add Integration**
3. Search for "z.ai Conversation"
4. Enter your configuration:
   - **API Key**: Your z.ai API key (required)
   - **Base URL**: Custom base URL (default: `https://api.z.ai/api/anthropic`)
5. Click **Submit**

The integration will validate your credentials by making a test connection to z.ai.

### Configuring the Conversation Agent

After adding the integration, you'll have a conversation agent automatically created. You can configure it:

1. Go to the z.ai integration page
2. Click **Configure** on the integration
3. Configure options:

#### Basic Options
- **Name**: Custom name for your agent
- **Prompt Template**: Custom system prompt (optional)
- **Control Home Assistant**: 
  - `none`: No device control
  - `assist`: Use Home Assistant's assist API (recommended)
  - `intent`: Use intent API

#### Advanced Options (disable "Use recommended settings")
- **Model**: Choose from available GLM-4 models
  - `glm-4.7`: Recommended default
  - `glm-4-flash`: Fastest, most cost-effective
  - `glm-4-plus`: Most capable, best quality
  - `glm-4-air`: Balanced performance
  - `glm-4-airx`: Extended context window
  - `glm-4-long`: Long context support
- **Maximum Tokens**: Max response length (1-8000, default: 3000)
- **Temperature**: Response randomness (0-1, default: 1.0)

## Usage

### In Home Assistant Assist

1. Open Home Assistant's Voice Assistant
2. Select your z.ai conversation agent from the dropdown
3. Start chatting!

### Controlling Devices

When "Control Home Assistant" is enabled, you can control your devices naturally:

```
"Turn on the living room lights"
"Set the thermostat to 72 degrees"
"What's the temperature in the bedroom?"
```

### Custom Prompts

You can customize the system prompt to change the agent's behavior:

```yaml
You are a helpful assistant for home automation.
Be concise and friendly. When controlling devices,
confirm the action after completing it.
```

## Supported Models

| Model | Description | Best For |
|-------|-------------|----------|
| glm-4.7 | Recommended default | General use, best overall |
| glm-4-flash | Fastest response, lower cost | Quick queries, simple tasks |
| glm-4-plus | Highest quality, most capable | Complex reasoning, detailed responses |
| glm-4-air | Balanced performance | General use, good balance |
| glm-4-airx | Extended context window | Long conversations, document analysis |
| glm-4-long | Very long context | Processing large amounts of text |

## Troubleshooting

### "Cannot connect" error

- Verify your API key is correct
- Check your internet connection
- Ensure the base URL is correct
- Check Home Assistant logs for detailed error messages

### "Authentication error"

- Your API key may be invalid or expired
- Generate a new API key from z.ai
- Reconfigure the integration with the new key

### Agent not responding

- Check Home Assistant logs for errors
- Verify the conversation agent is enabled
- Try adjusting max tokens or temperature settings
- Ensure z.ai service is operational

### Tool calling not working

- Make sure "Control Home Assistant" is set to "assist" or "intent"
- Check that your devices are properly configured in Home Assistant
- Review Home Assistant logs for permission issues

## Advanced Configuration

### Custom Base URL

If you're using a proxy or custom endpoint:

1. During setup, enter your custom base URL
2. The URL should be compatible with Anthropic's API format
3. Example: `https://your-proxy.com/api/anthropic`

### Multiple Conversation Agents

You can create multiple conversation agents with different configurations by adding multiple z.ai integrations, each with its own options.

## Development

This integration is built following Home Assistant's development guidelines and uses the Anthropic SDK for API communication.

### Requirements

- Home Assistant 2024.1.0 or later
- Python version provided by your Home Assistant installation
- `anthropic` Python package (v0.40.0)

## Support

For issues, feature requests, or questions:

- Open an issue on [GitHub](https://github.com/iannuz92/zai-conversation-ha/issues)
- Check existing issues for solutions
- Include Home Assistant logs when reporting bugs

## Credits

This integration is based on the official [Anthropic integration](https://github.com/home-assistant/core/tree/dev/homeassistant/components/anthropic) from Home Assistant core, adapted for z.ai's API.

## License

MIT License - See LICENSE file for details

## Changelog

### Version 1.0.0 (Initial Release)

- Initial release with z.ai GLM-4 support
- Conversation agent for Assist
- Function calling for device control
- Configurable models and parameters
- HACS compatibility
