"""
Main bot module for the Movie Enrichment Bot.

Enhanced version with conversation handler support and additional commands.
"""

import logging
import sys
from typing import Optional

from telegram import Update
from telegram.ext import (
    Application,
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)
from telegram.constants import ParseMode

from .config import Settings, get_settings
from .handlers.movie_handler import MovieHandler, create_movie_conversation
from .tmdb_service import TMDBService

logger = logging.getLogger(__name__)


def setup_logging(log_level: str) -> None:
    """
    Configure application logging.
    
    Args:
        log_level: The logging level string (DEBUG, INFO, etc.)
    """
    level = getattr(logging, log_level)
    
    # Configure root logger
    logging.basicConfig(
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        level=level,
        handlers=[
            logging.StreamHandler(sys.stdout),
        ]
    )
    
    # Reduce noise from httpx
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    
    # Reduce noise from telegram library
    logging.getLogger("telegram.ext.Application").setLevel(logging.INFO)
    
    logger.info(f"Logging configured at level: {log_level}")


async def start_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
) -> None:
    """
    Handle the /start command.
    
    Args:
        update: The Telegram update.
        context: The callback context.
    """
    user = update.effective_user
    welcome_message = (
        f"👋 Hello, {user.first_name}!\n\n"
        "🎬 <b>Welcome to CineBrain Movie Bot!</b>\n\n"
        "I'm an advanced bot that enriches your movie files with:\n"
        "• 🔍 Smart filename parsing\n"
        "• ✏️ Title editing capability\n"
        "• 📸 Movie posters from TMDB\n"
        "• ⭐ Ratings and reviews\n"
        "• 🎭 Genres and runtime\n"
        "• 📤 Automatic channel posting\n\n"
        "<b>How to use:</b>\n"
        "1. Forward me a movie file\n"
        "2. I'll detect the movie title\n"
        "3. Choose from search results\n"
        "4. Movie gets posted to channel\n\n"
        "Supported formats: MKV, MP4, AVI, MOV, and more!\n\n"
        "<i>Powered by CineBrain 🤖</i>"
    )
    await update.message.reply_text(welcome_message, parse_mode=ParseMode.HTML)


async def help_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
) -> None:
    """
    Handle the /help command.
    
    Args:
        update: The Telegram update.
        context: The callback context.
    """
    help_message = (
        "📖 <b>CineBrain Movie Bot Help</b>\n\n"
        "<b>Commands:</b>\n"
        "/start - Welcome message\n"
        "/help - This help message\n"
        "/status - Check bot status\n"
        "/parse - Test filename parser\n"
        "/cancel - Cancel current operation\n"
        "/about - About this bot\n\n"
        "<b>Features:</b>\n"
        "• <b>Smart Parser:</b> Extracts movie title from any filename\n"
        "• <b>Manual Edit:</b> Correct the title if needed\n"
        "• <b>Multiple Results:</b> Choose from up to 5 matches\n"
        "• <b>Rich Details:</b> Rating, runtime, genres, synopsis\n"
        "• <b>Auto Posting:</b> Sends to configured channel\n\n"
        "<b>How to use /parse:</b>\n"
        "Send: <code>/parse Movie.Name.2024.1080p.mkv</code>\n\n"
        "<b>Tips:</b>\n"
        "• Include year in filename for better results\n"
        "• Edit title if auto-detection fails\n"
        "• Select the correct movie from options\n\n"
        "<i>Visit CineBrain for more!</i>"
    )
    await update.message.reply_text(help_message, parse_mode=ParseMode.HTML)


async def status_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
) -> None:
    """
    Handle the /status command.
    
    Args:
        update: The Telegram update.
        context: The callback context.
    """
    settings = get_settings()
    
    # Check TMDB connection
    tmdb_status = "✅ Connected"
    try:
        tmdb = context.bot_data.get("tmdb_service")
        if not tmdb:
            tmdb_status = "⚠️ Not initialized"
    except:
        tmdb_status = "❌ Error"
    
    status_message = (
        "🤖 <b>CineBrain Bot Status</b>\n\n"
        f"<b>Bot Status:</b> ✅ Online\n"
        f"<b>TMDB API:</b> {tmdb_status}\n"
        f"<b>Channel ID:</b> <code>{settings.telegram_channel_id}</code>\n"
        f"<b>Cache TTL:</b> {settings.poster_cache_ttl}s\n"
        f"<b>Max Retries:</b> {settings.max_retries}\n\n"
        "🚀 <b>Ready to process movies!</b>\n\n"
        "<i>Powered by CineBrain</i>"
    )
    await update.message.reply_text(status_message, parse_mode=ParseMode.HTML)


async def parse_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
) -> None:
    """
    Handle the /parse command for testing filename parsing.
    
    Args:
        update: The Telegram update.
        context: The callback context.
    """
    if not context.args:
        await update.message.reply_text(
            "<b>Filename Parser Test</b>\n\n"
            "Usage: <code>/parse filename.mkv</code>\n\n"
            "Examples:\n"
            "• <code>/parse Movie.Name.2024.1080p.WEB-DL.mkv</code>\n"
            "• <code>/parse Movie_2023_BluRay_x264.mp4</code>\n"
            "• <code>/parse Movie (2022) Hindi 720p.avi</code>",
            parse_mode=ParseMode.HTML
        )
        return
    
    filename = " ".join(context.args)
    from .utils.parser import parse_filename
    
    parsed = parse_filename(filename)
    year_str = f" ({parsed.year})" if parsed.year else ""
    
    response = (
        "🔍 <b>Filename Parser Result</b>\n\n"
        f"<b>Input:</b>\n<code>{filename}</code>\n\n"
        f"<b>Parsed Result:</b>\n"
        f"🎬 <b>Title:</b> {parsed.title}\n"
        f"📅 <b>Year:</b> {parsed.year or 'Not detected'}\n\n"
        f"<b>Final:</b> <u>{parsed.title}{year_str}</u>\n\n"
        "<i>This is what will be searched on TMDB</i>"
    )
    
    await update.message.reply_text(response, parse_mode=ParseMode.HTML)


async def about_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
) -> None:
    """
    Handle the /about command.
    
    Args:
        update: The Telegram update.
        context: The callback context.
    """
    about_message = (
        "🎬 <b>CineBrain Movie Bot</b>\n\n"
        "Version: 1.0.0\n"
        "Engine: Python 3.11+ with async/await\n"
        "API: TMDB v3\n\n"
        "<b>Features:</b>\n"
        "• Advanced filename parsing\n"
        "• Real-time TMDB integration\n"
        "• Interactive movie selection\n"
        "• Professional templates\n"
        "• Smart caching system\n"
        "• Retry logic with exponential backoff\n\n"
        "<b>Tech Stack:</b>\n"
        "• python-telegram-bot v21+\n"
        "• httpx for async requests\n"
        "• pydantic for settings\n"
        "• tenacity for retries\n\n"
        "🌐 Visit CineBrain\n\n"
        "<i>Made with ❤️ for movie enthusiasts</i>"
    )
    await update.message.reply_text(about_message, parse_mode=ParseMode.HTML)


async def stats_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
) -> None:
    """
    Handle the /stats command (admin only).
    
    Args:
        update: The Telegram update.
        context: The callback context.
    """
    settings = get_settings()
    user_id = update.effective_user.id
    
    # Check if user is allowed (admin)
    if settings.allowed_users and user_id not in settings.allowed_users:
        await update.message.reply_text("⛔ This command is for administrators only.")
        return
    
    # Get stats from bot_data
    stats = context.bot_data.get("stats", {
        "movies_processed": 0,
        "searches_performed": 0,
        "cache_hits": 0,
        "errors": 0
    })
    
    stats_message = (
        "📊 <b>Bot Statistics</b>\n\n"
        f"🎬 <b>Movies Processed:</b> {stats.get('movies_processed', 0)}\n"
        f"🔍 <b>Searches Performed:</b> {stats.get('searches_performed', 0)}\n"
        f"💾 <b>Cache Hits:</b> {stats.get('cache_hits', 0)}\n"
        f"❌ <b>Errors:</b> {stats.get('errors', 0)}\n\n"
        "<i>Stats are reset on bot restart</i>"
    )
    await update.message.reply_text(stats_message, parse_mode=ParseMode.HTML)


async def error_handler(
    update: object,
    context: ContextTypes.DEFAULT_TYPE
) -> None:
    """
    Handle errors that occur during update processing.
    
    Args:
        update: The update that caused the error.
        context: The callback context with error information.
    """
    logger.error(
        f"Exception while handling an update: {context.error}",
        exc_info=context.error
    )
    
    # Update error stats
    if "stats" not in context.bot_data:
        context.bot_data["stats"] = {}
    context.bot_data["stats"]["errors"] = context.bot_data["stats"].get("errors", 0) + 1
    
    # Try to notify user if possible
    if isinstance(update, Update) and update.effective_message:
        try:
            error_message = (
                "❌ An error occurred\n\n"
                "The bot encountered an unexpected error. "
                "Please try again or contact support if the issue persists."
            )
            await update.effective_message.reply_text(error_message)
        except Exception:
            pass


async def post_init(application: Application) -> None:
    """
    Post-initialization callback.
    
    Args:
        application: The bot application.
    """
    logger.info("Initializing bot components...")
    
    # Store settings in bot_data
    settings = get_settings()
    application.bot_data["settings"] = settings
    
    # Initialize TMDB service
    tmdb_service = TMDBService(settings)
    await tmdb_service._ensure_client()
    application.bot_data["tmdb_service"] = tmdb_service
    
    # Initialize stats
    application.bot_data["stats"] = {
        "movies_processed": 0,
        "searches_performed": 0,
        "cache_hits": 0,
        "errors": 0
    }
    
    logger.info("✅ Bot initialized and ready!")
    
    # Log bot info
    bot = application.bot
    bot_info = await bot.get_me()
    logger.info(f"Bot username: @{bot_info.username}")
    logger.info(f"Bot ID: {bot_info.id}")


async def post_shutdown(application: Application) -> None:
    """
    Post-shutdown callback for cleanup.
    
    Args:
        application: The bot application.
    """
    logger.info("Shutting down bot components...")
    
    # Clean up TMDB service
    tmdb_service = application.bot_data.get("tmdb_service")
    if tmdb_service:
        await tmdb_service.close()
        logger.info("TMDB service closed")
    
    # Log final stats
    stats = application.bot_data.get("stats", {})
    logger.info(f"Final stats: {stats}")
    
    logger.info("Bot shutdown complete")


def build_application(settings: Optional[Settings] = None) -> Application:
    """
    Build and configure the bot application.
    
    Args:
        settings: Application settings. Uses default if not provided.
    
    Returns:
        The configured Application instance.
    """
    if settings is None:
        settings = get_settings()
    
    setup_logging(settings.log_level)
    logger.info("Building CineBrain Movie Bot application...")
    logger.info(f"Channel ID: {settings.telegram_channel_id}")
    
    # Build application WITHOUT job queue (fixes Python 3.13 weak reference issue)
    builder = ApplicationBuilder()
    builder.token(settings.telegram_bot_token)
    builder.post_init(post_init)
    builder.post_shutdown(post_shutdown)
    
    # IMPORTANT: Disable job queue to fix Python 3.13 compatibility
    builder.job_queue(None)
    
    # Build the application
    application = builder.build()
    
    # Initialize movie handler
    movie_handler = MovieHandler(settings=settings)
    
    # Add conversation handler for movie processing
    movie_conv_handler = create_movie_conversation(movie_handler)
    application.add_handler(movie_conv_handler)
    
    # Add command handlers
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("status", status_command))
    application.add_handler(CommandHandler("parse", parse_command))
    application.add_handler(CommandHandler("about", about_command))
    application.add_handler(CommandHandler("stats", stats_command))
    
    # Add error handler
    application.add_error_handler(error_handler)
    
    logger.info("✅ Bot application built successfully")
    logger.info("Available commands: /start, /help, /status, /parse, /about, /stats")
    
    return application


def run_bot(settings: Optional[Settings] = None) -> None:
    """
    Build and run the bot.
    
    Args:
        settings: Optional settings override.
    """
    application = build_application(settings)
    
    logger.info("🚀 Starting CineBrain Movie Bot polling...")
    logger.info("Press Ctrl+C to stop")
    
    # Run the bot
    application.run_polling(
        allowed_updates=Update.ALL_TYPES,
        drop_pending_updates=True
    )


# For backwards compatibility
class MovieEnrichmentBot:
    """
    Wrapper class for the Movie Enrichment Bot.
    """
    
    def __init__(self, settings: Optional[Settings] = None) -> None:
        self._settings = settings or get_settings()
        self._application: Optional[Application] = None
    
    def build(self) -> Application:
        self._application = build_application(self._settings)
        return self._application
    
    def run(self) -> None:
        run_bot(self._settings)


def create_bot(settings: Optional[Settings] = None) -> MovieEnrichmentBot:
    """Factory function to create a bot instance."""
    return MovieEnrichmentBot(settings)