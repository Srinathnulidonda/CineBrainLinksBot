# 🎬 Movie Enrichment Bot

A production-grade Telegram bot that automatically enriches forwarded movie files with TMDB metadata and posters.

## Features

- 🔍 **Smart Filename Parsing**: Extracts movie titles from messy filenames
- 🎬 **TMDB Integration**: Fetches movie posters, ratings, and overviews
- 📤 **Channel Posting**: Automatically posts enriched content to your channel
- 🔄 **No Re-upload**: Forwards original files without re-uploading
- 💾 **Poster Caching**: In-memory cache for faster responses
- 🔁 **Retry Logic**: Automatic retries for failed API calls
- 🛡️ **Error Handling**: Graceful error handling, never crashes

## Prerequisites

- Python 3.10+
- Telegram Bot Token (from [@BotFather](https://t.me/BotFather))
- TMDB API Key (from [TMDB](https://www.themoviedb.org/settings/api))
- A Telegram channel where the bot is an admin

## Quick Start

### 1. Clone and Setup

```bash
git clone https://github.com/your-repo/movie-enrichment-bot.git
cd movie-enrichment-bot

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt