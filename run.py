#!/usr/bin/env python3
"""
Entry point for the Movie Enrichment Bot.

This script initializes and runs the Telegram bot.
Usage: python run.py
"""

import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from src.bot import run_bot
from src.config import get_settings


def main() -> None:
    """Main entry point for the bot."""
    try:
        # Validate settings on startup
        settings = get_settings()
        print(f"✅ Configuration loaded")
        print(f"📡 Channel ID: {settings.telegram_channel_id}")
        print(f"📊 Log Level: {settings.log_level}")
        
        # Run the bot
        run_bot(settings)
        
    except KeyboardInterrupt:
        print("\n👋 Bot stopped by user")
        sys.exit(0)
    except ValueError as e:
        print(f"❌ Configuration error: {e}")
        print("Please check your .env file")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Failed to start bot: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()