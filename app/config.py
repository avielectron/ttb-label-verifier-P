import os

from dotenv import load_dotenv

load_dotenv()

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
ANTHROPIC_MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-5-20250929")

if not ANTHROPIC_API_KEY:
    # Don't crash on import (so the app can still serve a helpful error page),
    # but every vision call will fail fast with a clear message.
    print(
        "WARNING: ANTHROPIC_API_KEY is not set. Copy .env.example to .env "
        "and add your key from https://console.anthropic.com/"
    )
