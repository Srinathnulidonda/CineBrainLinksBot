"""
Movie file handler with interactive selection and text editing.

Fixed version with proper imports and photo/text message handling.
"""

import re
import logging
from io import BytesIO
from typing import Optional, Dict, Any

from telegram import (
    Update, Message, InlineKeyboardButton, 
    InlineKeyboardMarkup, InputMediaPhoto
)
from telegram.constants import ParseMode
from telegram.error import TelegramError, Forbidden, BadRequest
from telegram.ext import (
    ContextTypes, ConversationHandler, 
    CommandHandler, MessageHandler, CallbackQueryHandler,
    filters
)

# FIXED: Use .. to go up one level from handlers to src
from ..config import Settings, get_settings
from ..tmdb_service import TMDBService, MovieInfo, get_tmdb_service
from ..utils.parser import FilenameParser, ParsedFilename

logger = logging.getLogger(__name__)

# Conversation states
EDIT_TITLE, SELECT_MOVIE = range(2)


class MovieHandler:
    """
    Advanced movie handler with interactive features.
    
    Features:
    - Parse filenames intelligently
    - Allow manual title editing
    - Show multiple TMDB results with posters
    - Let user select the correct movie
    - Post to channel
    """
    
    # Supported video file extensions
    SUPPORTED_EXTENSIONS = {
        '.mkv', '.mp4', '.avi', '.mov', '.wmv', '.flv',
        '.webm', '.m4v', '.mpg', '.mpeg', '.ts', '.vob',
        '.m2ts', '.3gp', '.f4v', '.ogv'
    }
    
    def __init__(
        self,
        settings: Optional[Settings] = None,
        filename_parser: Optional[FilenameParser] = None
    ) -> None:
        """Initialize the movie handler."""
        self._settings = settings or get_settings()
        self._parser = filename_parser or FilenameParser()
        # Store current processing data per user
        self._user_data: Dict[int, Dict[str, Any]] = {}
    
    async def _get_tmdb_service(
        self,
        context: ContextTypes.DEFAULT_TYPE
    ) -> TMDBService:
        """Get TMDB service from context or create new one."""
        tmdb_service = context.bot_data.get("tmdb_service")
        if tmdb_service:
            return tmdb_service
        return await get_tmdb_service()
    
    def _is_supported_file(self, filename: str) -> bool:
        """Check if the file is a supported video file."""
        if not filename:
            return False
        
        lower_name = filename.lower()
        
        # Skip split archive parts
        if re.search(r'\.(zip|rar|7z|gz|bz2|tar|xz)\.\d{3,4}$', lower_name):
            logger.debug(f"Skipping split archive part: {filename}")
            return False
        
        # Skip pure archives
        archive_extensions = ('.zip', '.rar', '.7z', '.gz', '.bz2', '.tar', '.xz', '.iso')
        if lower_name.endswith(archive_extensions):
            logger.debug(f"Skipping archive file: {filename}")
            return False
        
        # Check if it's a supported video file
        return any(lower_name.endswith(ext) for ext in self.SUPPORTED_EXTENSIONS)
    
    def _is_user_allowed(self, user_id: int) -> bool:
        """Check if the user is allowed to use the bot."""
        allowed = self._settings.allowed_users
        if not allowed:
            return True
        return user_id in allowed
    
    async def handle_document(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE
    ) -> int:
        """
        Handle incoming document messages.
        
        This is the main entry point for processing movie files.
        """
        message = update.message
        if not message or not message.document:
            return ConversationHandler.END
        
        user = message.from_user
        user_id = user.id if user else 0
        username = user.username if user else "Unknown"
        
        logger.info(f"Received document from user {username} (ID: {user_id})")
        
        # Check user permissions
        if not self._is_user_allowed(user_id):
            logger.warning(f"Unauthorized user: {user_id}")
            await message.reply_text(
                "⛔ You are not authorized to use this bot."
            )
            return ConversationHandler.END
        
        document = message.document
        filename = document.file_name
        
        if not filename:
            logger.debug("Document has no filename, skipping")
            return ConversationHandler.END
        
        logger.info(f"Processing file: {filename}")
        
        # Check if it's a video file
        if not self._is_supported_file(filename):
            logger.debug(f"Unsupported file type: {filename}")
            if not re.search(r'\.(zip|rar|7z)\.\d{3,4}$', filename.lower()):
                await message.reply_text(
                    "❌ This doesn't appear to be a movie file. "
                    "Supported formats: MKV, MP4, AVI, MOV, etc."
                )
            return ConversationHandler.END
        
        # Update stats
        if "stats" not in context.bot_data:
            context.bot_data["stats"] = {}
        context.bot_data["stats"]["movies_processed"] = context.bot_data["stats"].get("movies_processed", 0) + 1
        
        # Parse filename
        parsed = self._parser.parse(filename)
        logger.info(f"Parsed filename: {parsed}")
        
        # Store processing data
        self._user_data[user_id] = {
            'message': message,
            'filename': filename,
            'parsed': parsed,
            'title': parsed.title,
            'year': parsed.year,
            'message_is_photo': False  # Track message type
        }
        
        # Show parsed title and options
        year_str = f" ({parsed.year})" if parsed.year else ""
        
        keyboard = [
            [
                InlineKeyboardButton("✅ Search", callback_data="search"),
                InlineKeyboardButton("✏️ Edit Title", callback_data="edit")
            ],
            [
                InlineKeyboardButton("❌ Cancel", callback_data="cancel")
            ]
        ]
        
        await message.reply_text(
            f"📽️ <b>Detected Movie:</b>\n"
            f"<code>{parsed.title}{year_str}</code>\n\n"
            f"Choose an action:",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode=ParseMode.HTML
        )
        
        return SELECT_MOVIE
    
    async def handle_callback(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE
    ) -> int:
        """Handle inline keyboard callbacks."""
        query = update.callback_query
        await query.answer()
        
        user_id = query.from_user.id
        data = query.data
        
        if user_id not in self._user_data:
            await query.edit_message_text("❌ Session expired. Please send the file again.")
            return ConversationHandler.END
        
        user_info = self._user_data[user_id]
        
        if data == "cancel":
            # Handle both photo and text messages
            if user_info.get('message_is_photo'):
                await query.edit_message_caption("❌ Cancelled.")
            else:
                await query.edit_message_text("❌ Cancelled.")
            del self._user_data[user_id]
            return ConversationHandler.END
        
        elif data == "edit":
            # Handle both photo and text messages
            edit_text = (
                "✏️ Please type the correct movie title:\n"
                "(You can include year like: 'Inception 2010')"
            )
            if user_info.get('message_is_photo'):
                await query.edit_message_caption(edit_text)
            else:
                await query.edit_message_text(edit_text)
            return EDIT_TITLE
        
        elif data == "search":
            # Handle both photo and text messages
            if user_info.get('message_is_photo'):
                await query.edit_message_caption("🔍 Searching TMDB...")
            else:
                await query.edit_message_text("🔍 Searching TMDB...")
            return await self._search_movies(query.message, user_id, context)
        
        elif data.startswith("movie_"):
            # User selected a specific movie
            movie_index = int(data.split("_")[1])
            return await self._process_selected_movie(
                query.message, user_id, movie_index, context
            )
        
        elif data == "none":
            # None of the options match
            edit_text = "✏️ Please type the correct movie title:"
            if user_info.get('message_is_photo'):
                await query.edit_message_caption(edit_text)
            else:
                await query.edit_message_text(edit_text)
            return EDIT_TITLE
        
        return SELECT_MOVIE
    
    async def handle_text_edit(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE
    ) -> int:
        """Handle manual title editing."""
        message = update.message
        user_id = message.from_user.id
        
        if user_id not in self._user_data:
            await message.reply_text("❌ Session expired. Please send the file again.")
            return ConversationHandler.END
        
        # Parse user input for title and year
        text = message.text.strip()
        year_match = re.search(r'\b(19[0-9]{2}|20[0-3][0-9])\b', text)
        
        year = None
        title = text
        
        if year_match:
            year = int(year_match.group(1))
            title = re.sub(r'\b' + str(year) + r'\b', '', text).strip()
        
        # Update stored data
        self._user_data[user_id]['title'] = title
        self._user_data[user_id]['year'] = year
        
        # Search with new title
        await message.reply_text(f"🔍 Searching for: {title}")
        return await self._search_movies(message, user_id, context)
    
    async def _search_movies(
        self,
        message: Message,
        user_id: int,
        context: ContextTypes.DEFAULT_TYPE
    ) -> int:
        """Search TMDB and show results."""
        user_info = self._user_data[user_id]
        title = user_info['title']
        year = user_info.get('year')
        
        # Update search stats
        if "stats" not in context.bot_data:
            context.bot_data["stats"] = {}
        context.bot_data["stats"]["searches_performed"] = context.bot_data["stats"].get("searches_performed", 0) + 1
        
        # Get TMDB service
        tmdb = await self._get_tmdb_service(context)
        
        # Search for multiple results
        movies = await tmdb.search_movies(title, year, limit=5)
        
        if not movies:
            # No results found
            keyboard = [
                [
                    InlineKeyboardButton("✏️ Edit Title", callback_data="edit"),
                    InlineKeyboardButton("❌ Cancel", callback_data="cancel")
                ]
            ]
            
            no_results_text = (
                f"❌ No results found for: <b>{title}</b>\n\n"
                "Try editing the title or cancel."
            )
            
            # Update based on message type
            if user_info.get('message_is_photo'):
                await message.edit_caption(
                    no_results_text,
                    reply_markup=InlineKeyboardMarkup(keyboard),
                    parse_mode=ParseMode.HTML
                )
            else:
                await message.edit_text(
                    no_results_text,
                    reply_markup=InlineKeyboardMarkup(keyboard),
                    parse_mode=ParseMode.HTML
                )
            return SELECT_MOVIE
        
        # Store search results
        user_info['movies'] = movies
        
        # Create selection keyboard
        keyboard = []
        for i, movie in enumerate(movies):
            year_str = f" ({movie.year})" if movie.year else ""
            button_text = f"{i+1}. {movie.title}{year_str} ⭐{movie.rating:.1f}"
            keyboard.append([InlineKeyboardButton(button_text, callback_data=f"movie_{i}")])
        
        keyboard.append([
            InlineKeyboardButton("❌ None of these", callback_data="none"),
            InlineKeyboardButton("🚫 Cancel", callback_data="cancel")
        ])
        
        # Build selection caption
        caption = self._build_selection_caption(movies)
        
        # Mark that we're sending a photo
        user_info['message_is_photo'] = True
        
        # Send first movie poster with all options
        first_movie = movies[0]
        
        if first_movie.poster_url:
            poster_data = await tmdb.fetch_poster(first_movie.poster_url)
            if poster_data:
                try:
                    await message.delete()
                    await message.chat.send_photo(
                        photo=BytesIO(poster_data),
                        caption=caption,
                        reply_markup=InlineKeyboardMarkup(keyboard),
                        parse_mode=ParseMode.HTML
                    )
                except Exception as e:
                    logger.error(f"Error sending poster: {e}")
                    user_info['message_is_photo'] = False
                    await message.edit_text(
                        caption,
                        reply_markup=InlineKeyboardMarkup(keyboard),
                        parse_mode=ParseMode.HTML
                    )
            else:
                user_info['message_is_photo'] = False
                if hasattr(message, 'edit_text'):
                    await message.edit_text(
                        caption,
                        reply_markup=InlineKeyboardMarkup(keyboard),
                        parse_mode=ParseMode.HTML
                    )
                else:
                    await message.edit_caption(
                        caption,
                        reply_markup=InlineKeyboardMarkup(keyboard),
                        parse_mode=ParseMode.HTML
                    )
        else:
            user_info['message_is_photo'] = False
            if hasattr(message, 'edit_text'):
                await message.edit_text(
                    caption,
                    reply_markup=InlineKeyboardMarkup(keyboard),
                    parse_mode=ParseMode.HTML
                )
            else:
                await message.edit_caption(
                    caption,
                    reply_markup=InlineKeyboardMarkup(keyboard),
                    parse_mode=ParseMode.HTML
                )
        
        return SELECT_MOVIE
    
    def _build_selection_caption(self, movies: list) -> str:
        """Build caption for movie selection."""
        caption = "🎬 <b>Select the correct movie:</b>\n\n"
        
        for i, movie in enumerate(movies, 1):
            year_str = f" ({movie.year})" if movie.year else ""
            caption += f"<b>{i}.</b> {movie.title}{year_str}\n"
            caption += f"   ⭐ {movie.rating:.1f}/10"
            
            # Add runtime if available
            if movie.runtime:
                hours = movie.runtime // 60
                mins = movie.runtime % 60
                if hours > 0:
                    caption += f" | ⏱ {hours}h {mins}m"
                else:
                    caption += f" | ⏱ {mins}m"
            
            caption += "\n"
            
            # Add genres if available
            if movie.genres:
                caption += f"   🎭 {', '.join(movie.genres[:3])}\n"
            
            # Add short overview
            if movie.overview:
                overview = movie.overview[:100] + "..." if len(movie.overview) > 100 else movie.overview
                caption += f"   <i>{overview}</i>\n"
            
            caption += "\n"
        
        return caption
    
    async def _process_selected_movie(
        self,
        message: Message,
        user_id: int,
        movie_index: int,
        context: ContextTypes.DEFAULT_TYPE
    ) -> int:
        """Process the selected movie and post to channel."""
        user_info = self._user_data[user_id]
        original_message = user_info['message']
        movies = user_info['movies']
        
        if movie_index >= len(movies):
            error_text = "❌ Invalid selection."
            if user_info.get('message_is_photo'):
                await message.edit_caption(error_text)
            else:
                await message.edit_text(error_text)
            return ConversationHandler.END
        
        selected_movie = movies[movie_index]
        
        # Update status based on message type
        status_text = f"📤 Posting <b>{selected_movie.title}</b> to channel..."
        
        if user_info.get('message_is_photo'):
            await message.edit_caption(status_text, parse_mode=ParseMode.HTML)
        else:
            await message.edit_text(status_text, parse_mode=ParseMode.HTML)
        
        # Get TMDB service
        tmdb = await self._get_tmdb_service(context)
        
        # Post to channel
        success = await self._post_to_channel(
            original_message, selected_movie, tmdb
        )
        
        # Update final status
        if success:
            final_text = f"✅ Successfully posted <b>{selected_movie.title}</b> to channel!"
        else:
            final_text = "⚠️ There was an issue posting to the channel."
        
        if user_info.get('message_is_photo'):
            await message.edit_caption(final_text, parse_mode=ParseMode.HTML)
        else:
            await message.edit_text(final_text, parse_mode=ParseMode.HTML)
        
        # Cleanup
        del self._user_data[user_id]
        return ConversationHandler.END
    
    async def _post_to_channel(
        self,
        message: Message,
        movie_info: MovieInfo,
        tmdb: TMDBService
    ) -> bool:
        """Post movie information and file to the channel."""
        channel_id = self._settings.telegram_channel_id
        bot = message.get_bot()
        
        try:
            # Verify channel access
            await self._verify_channel_access(bot, channel_id)
        except PermissionError as e:
            logger.error(f"Channel access error: {e}")
            return False
        
        # Get the professional formatted caption
        caption = movie_info.get_formatted_caption()
        
        try:
            # Post poster if available
            if movie_info.poster_url:
                poster_data = await tmdb.fetch_poster(movie_info.poster_url)
                
                if poster_data:
                    logger.debug("Sending poster to channel")
                    await bot.send_photo(
                        chat_id=channel_id,
                        photo=BytesIO(poster_data),
                        caption=caption,
                        parse_mode=ParseMode.HTML
                    )
                else:
                    await bot.send_message(
                        chat_id=channel_id,
                        text=caption,
                        parse_mode=ParseMode.HTML,
                        disable_web_page_preview=False
                    )
            else:
                await bot.send_message(
                    chat_id=channel_id,
                    text=caption,
                    parse_mode=ParseMode.HTML,
                    disable_web_page_preview=False
                )
            
            # Forward the original file
            logger.debug("Forwarding file to channel")
            await message.forward(chat_id=channel_id)
            
            logger.info(f"Successfully posted movie to channel: {movie_info.title}")
            return True
            
        except Exception as e:
            logger.error(f"Error posting to channel: {e}")
            return False
    
    async def _verify_channel_access(self, bot, channel_id: int) -> None:
        """Verify the bot has access to post in the channel."""
        try:
            chat = await bot.get_chat(channel_id)
            member = await bot.get_chat_member(channel_id, bot.id)
            
            if member.status not in ('administrator', 'creator'):
                raise PermissionError(f"Bot is not an admin in channel")
            
            logger.debug(f"Verified access to channel: {chat.title}")
            
        except Forbidden:
            raise PermissionError("Bot is not a member of the channel")
        except BadRequest as e:
            raise PermissionError(f"Cannot access channel: {e}")
    
    async def cancel_handler(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE
    ) -> int:
        """Handle conversation cancellation."""
        user_id = update.effective_user.id
        
        if user_id in self._user_data:
            del self._user_data[user_id]
        
        await update.message.reply_text("❌ Operation cancelled.")
        return ConversationHandler.END


# Create conversation handler with proper per_message setting
def create_movie_conversation(movie_handler: MovieHandler) -> ConversationHandler:
    """Create the conversation handler for movie processing."""
    return ConversationHandler(
        entry_points=[
            MessageHandler(filters.Document.ALL, movie_handler.handle_document)
        ],
        states={
            SELECT_MOVIE: [
                CallbackQueryHandler(movie_handler.handle_callback)
            ],
            EDIT_TITLE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, movie_handler.handle_text_edit)
            ]
        },
        fallbacks=[
            CommandHandler("cancel", movie_handler.cancel_handler)
        ],
        per_user=True,
        per_chat=True,
        per_message=False  # Fix the warning
    )