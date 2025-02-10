import os, logging
from flask import Flask, request, jsonify
import requests
import jwt  # PyJWT library for verifying JSON Web Tokens
from typing import Optional
from dotenv import load_dotenv

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)  # Configure basic logging

# Load environment variables from .env file
load_dotenv()

def get_required_env(key: str) -> str:
    """Get a required environment variable or raise an error."""
    value = os.environ.get(key)
    if not value:
        raise ValueError(f"Missing required environment variable: {key}")
    return value

def get_optional_env(key: str, default: str) -> str:
    """Get an optional environment variable with a default value."""
    return os.environ.get(key, default)

# Google Chat verification setup
GCP_PROJECT_NUMBER = get_required_env("GCP_PROJECT_NUMBER")
# URL to Google Chat's public keys (JWKS) for verifying tokens
GOOGLE_CHAT_JWKS_URL = "https://www.googleapis.com/service_accounts/v1/jwk/chat@system.gserviceaccount.com"
jwks_client = jwt.PyJWKClient(GOOGLE_CHAT_JWKS_URL)

# OpenWebUI API setup
OWUI_API_URL = get_optional_env("OWUI_API_URL", "https://cojovi.ngrok.dev:3000/api/v1")  # base URL of OpenWebUI API
OWUI_API_KEY = get_required_env("OWUI_API_KEY")  # API key from OpenWebUI settings

# In-memory store for chat sessions (maps Google Chat space -> OpenWebUI chat ID)
chat_sessions = {}

@app.route('/webhook', methods=['POST'])
def webhook():
    # Verify the request is from Google Chat by checking the JWT in Authorization header
    auth_header = request.headers.get('Authorization', '')
    token = auth_header.split('Bearer ')[-1] if auth_header.startswith('Bearer ') else None
    if not token:
        app.logger.error("Missing Authorization token")
        return jsonify({"error": "Unauthorized"}), 401
    try:
        signing_key = jwks_client.get_signing_key_from_jwt(token)
        decoded_token = jwt.decode(token, signing_key.key, algorithms=["RS256"], 
                                   audience=GCP_PROJECT_NUMBER, issuer="chat@system.gserviceaccount.com")
        # If verification passes, decoded_token contains token claims (not used further here)
    except Exception as e:
        app.logger.error(f"Failed to verify Google Chat JWT: {e}")
        return jsonify({"error": "Unauthorized"}), 401

    event = request.get_json()  # Parse the JSON body of the request
    app.logger.info(f"Received event from Chat: {event}")

    # Handle different event types
    event_type = event.get("type")
    if event_type == "ADDED_TO_SPACE":
        # Bot was added to a space (group chat) or DM
        user_name = event.get("user", {}).get("displayName", "there")
        welcome_text = f"Hello {user_name}, I'm your OpenWebUI bot! Ask me anything."
        return jsonify({"text": welcome_text})
    if event_type == "REMOVED_FROM_SPACE":
        # Bot removed – clean up session if any
        space = event.get("space", {}).get("name")
        if space in chat_sessions:
            chat_sessions.pop(space, None)
        return jsonify({})  # No response needed

    # Default case: MESSAGE event (a user sent a message in a space or DM)
    user_message = event.get("message", {}).get("text", "")
    if not user_message:
        return jsonify({})  # nothing to do if no message text

    # Identify the chat (space or DM) to maintain context
    space_id = event.get("space", {}).get("name")  # e.g., "spaces/XXXXXXXX"
    if space_id not in chat_sessions:
        # Create a new chat session in OpenWebUI for this conversation
        try:
            resp = requests.post(f"{OWUI_API_URL}/chats/new", 
                                 headers={"Authorization": f"Bearer {OWUI_API_KEY}",
                                          "Content-Type": "application/json"},
                                 json={"chat": {}})
            resp.raise_for_status()
        except Exception as e:
            app.logger.error(f"Failed to create new chat in OpenWebUI: {e}")
            return jsonify({"text": "Sorry, I couldn't start a session with the AI."})
        chat_id = resp.json().get("id") or resp.json().get("chat_id")
        chat_sessions[space_id] = chat_id
        app.logger.info(f"Started new OpenWebUI chat session {chat_id} for space {space_id}")
    else:
        chat_id = chat_sessions[space_id]

    # Forward the user message to OpenWebUI API to get AI response
    try:
        payload = {"chat": {"content": user_message, "role": "user"}}
        resp = requests.post(f"{OWUI_API_URL}/chats/{chat_id}",
                             headers={"Authorization": f"Bearer {OWUI_API_KEY}",
                                      "Content-Type": "application/json"},
                             json=payload, timeout=15)
        resp.raise_for_status()
    except Exception as e:
        app.logger.error(f"Error calling OpenWebUI API: {e}")
        return jsonify({"text": "⚠️ Error: The AI service is unavailable at the moment."})

    # Extract the assistant's reply from OpenWebUI response
    owui_data = resp.json()
    # The exact response structure depends on OpenWebUI; assume the assistant's reply text is present:
    assistant_reply = ""
    # Try typical fields where content might be:
    if "chat" in owui_data:
        # Some versions return the last chat message under 'chat'
        content = owui_data["chat"].get("content")
        role = owui_data["chat"].get("role")
        if role == "assistant" and content:
            assistant_reply = content
    if not assistant_reply:
        # If not found above, try other possible structure (e.g., 'assistant' key or OpenAI-like format)
        assistant_reply = owui_data.get("assistant", {}).get("content") or owui_data.get("content", "")
    if not assistant_reply:
        assistant_reply = "*(No response from AI)*"

    app.logger.info(f"Responding to space {space_id} with reply: {assistant_reply}")
    return jsonify({"text": assistant_reply})

if __name__ == '__main__':
    app.run(port=5000)

