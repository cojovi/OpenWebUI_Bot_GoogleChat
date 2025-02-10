# Google Chat OpenWebUI Bot

A Google Chat bot that integrates with OpenWebUI to provide AI-powered responses in chat conversations.

## Prerequisites

- Python 3.8+
- OpenWebUI instance running and accessible
- Google Cloud Project with Google Chat API enabled
- Ngrok (for local development) or a public HTTPS endpoint

## Environment Variables

Create a `.env` file with the following variables:

```env
GCP_PROJECT_NUMBER=your_project_number
OWUI_API_KEY=your_openwebui_api_key
OWUI_API_URL=http://localhost:3000/api/v1  # Adjust if needed
```

## Setup

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

2. Start the Flask server:
   ```bash
   python bot.py
   ```

3. Expose your local server (development only):
   ```bash
   ngrok http 5000
   ```

4. Configure Google Chat App:
   - Go to Google Cloud Console
   - Enable Google Chat API
   - Configure the Chat App with the Ngrok URL
   - Set up authentication and permissions

## Usage

- Add the bot to a Google Chat space or start a DM
- The bot will respond to direct messages or @mentions
- Each conversation maintains its context with OpenWebUI

## Security

- Validates all incoming requests using Google Chat's JWT tokens
- Requires proper environment variables for API keys
- Uses HTTPS for all external communications

## Development

The bot uses Flask for the webhook server and maintains conversation context using OpenWebUI's chat sessions. All messages are logged for debugging purposes. 