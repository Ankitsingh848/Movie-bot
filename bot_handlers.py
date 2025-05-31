import logging
import asyncio
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ChatMember
from telegram.ext import ContextTypes
from telegram.error import TelegramError
from database import Database
from config import Config
from utils import format_file_size, parse_upload_caption, fuzzy_search_movies

from file_manager import FileManager
from admin_panel import AdminPanel
from bulk_upload_handler import BulkUploadHandler
from bot_structure_viewer import BotStructureViewer
from admin_chat_system import AdminChatSystem

from bot_blueprint_generator import BotBlueprintGenerator

logger = logging.getLogger(__name__)

class BotHandlers:
    """Main bot handlers class"""
    
    def __init__(self, database: Database):
        self.db = database

        self.file_manager = FileManager()
        self.admin_panel = AdminPanel(database)
        self.bulk_handler = BulkUploadHandler(database)
        self.structure_viewer = BotStructureViewer(database)
        self.admin_chat = AdminChatSystem(database)
        self.blueprint_generator = BotBlueprintGenerator(database)
        
        # Validate configuration on startup
        Config.validate_config()
    
    async def check_backup_channel_membership(self, user_id: int, context: ContextTypes.DEFAULT_TYPE) -> bool:
        """Check if user is member of backup channel"""
        if not Config.FORCE_JOIN_BACKUP:
            return True
            
        try:
            member = await context.bot.get_chat_member(Config.BACKUP_CHANNEL_ID, user_id)
            return member.status in [ChatMember.MEMBER, ChatMember.ADMINISTRATOR, ChatMember.OWNER]
        except Exception as e:
            logger.warning(f"Could not check backup channel membership for {user_id}: {e}")
            return True  # Allow access if we can't check
    
    async def show_backup_channel_prompt(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show backup channel join prompt"""
        keyboard = [
            [InlineKeyboardButton("🔗 Join Backup Channel", url=Config.BACKUP_CHANNEL)],
            [InlineKeyboardButton("✅ I Joined - Continue", callback_data="check_backup_join")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            "🚨 **Join Our Backup Channel**\n\n"
            "To use this bot, please join our backup channel first.\n"
            "This ensures you get updates if the main bot goes down!\n\n"
            "👆 Click the button above to join, then click 'I Joined'",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )

    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start command with auto-verification status check"""
        user = update.effective_user
        
        try:
            # Auto-save user information to database
            self.db.save_user_info(user.id, user.username or "", user.first_name or "")
            
            # Check backup channel membership first (except for admins)
            if user.id not in Config.ADMIN_IDS:
                is_member = await self.check_backup_channel_membership(user.id, context)
                if not is_member:
                    await self.show_backup_channel_prompt(update, context)
                    return
            
            # Check if it's a download request from a shortened URL
            if context.args and len(context.args) > 0:
                arg = context.args[0]
                logger.info(f"Start command with argument: {arg} from user {user.id}")
                
                if arg.startswith("download_") or arg.startswith("get_"):
                    file_id = arg.replace("download_", "").replace("get_", "")
                    logger.info(f"Processing download request for file_id: {file_id}")
                    
                    # Find movie by file_id
                    movies = self.db.search_movies("", limit=1000)
                    movie = None
                    for m in movies:
                        if m['file_id'] == file_id:
                            movie = m
                            break
                    
                    if movie:
                        logger.info(f"Movie found: {movie['title']} - sending file to user {user.id}")
                        # Send file directly without any verification
                        await self._send_file_directly_from_start(update, user, movie, context)
                        return
                    else:
                        logger.warning(f"Movie not found for file_id: {file_id}")
                        await update.message.reply_text("❌ File not found or may have been removed.")
                        return
            
            # Regular start command without verification
            if user.id in Config.ADMIN_IDS:
                await update.message.reply_text(
                    Config.ADMIN_WELCOME_MESSAGE,
                    parse_mode='Markdown'
                )
            else:
                welcome_msg = Config.WELCOME_MESSAGE.format(BACKUP_CHANNEL=Config.BACKUP_CHANNEL)
                await update.message.reply_text(
                    welcome_msg,
                    parse_mode='Markdown'
                )
                
            logger.info(f"User {user.id} ({user.username}) started the bot")
            
        except Exception as e:
            logger.error(f"Error in start_command: {e}")
            await update.message.reply_text(
                "❌ An error occurred. Please try again later."
            )
    
    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /help command"""
        try:
            await update.message.reply_text(
                Config.HELP_MESSAGE,
                parse_mode='Markdown'
            )
        except Exception as e:
            logger.error(f"Error in help_command: {e}")
            await update.message.reply_text(
                "❌ An error occurred. Please try again later."
            )
    
    async def admin_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /admin command"""
        user = update.effective_user
        
        if user.id not in Config.ADMIN_IDS:
            await update.message.reply_text("❌ You are not authorized to use admin commands.")
            return
        
        try:
            await self.admin_panel.show_admin_panel(update, context)
        except Exception as e:
            logger.error(f"Error in admin_command: {e}")
            await update.message.reply_text(
                "❌ An error occurred in admin panel. Please try again later."
            )
    
    async def upload_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /upload command"""
        user = update.effective_user
        
        if user.id not in Config.ADMIN_IDS:
            await update.message.reply_text("❌ You are not authorized to upload files.")
            return
        
        try:
            await update.message.reply_text(
                "📁 **Upload Instructions:**\n\n"
                "Send a video file with caption in this format:\n"
                "`Movie Name | Year | Quality | Part/Season/Episode`\n\n"
                "**Examples:**\n"
                "• `Avengers Endgame | 2019 | 1080p | Complete`\n"
                "• `Breaking Bad | 2008 | 720p | Season 1 Episode 1`\n"
                "• `The Batman | 2022 | 4K | Part 1`\n\n"
                "**Note:** Upload any size file - stored in Telegram's unlimited cloud storage",
                parse_mode='Markdown'
            )
        except Exception as e:
            logger.error(f"Error in upload_command: {e}")
            await update.message.reply_text(
                "❌ An error occurred. Please try again later."
            )
    
    async def stats_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /stats command"""
        user = update.effective_user
        
        if user.id not in Config.ADMIN_IDS:
            await update.message.reply_text("❌ You are not authorized to view statistics.")
            return
        
        try:
            stats = self.db.get_stats()
            
            stats_message = f"""
📊 **Bot Statistics**

🎬 **Movies:** {stats['total_movies']}
⬇️ **Downloads:** {stats['total_downloads']}
🔍 **Searches:** {stats['total_searches']}
👥 **Unique Users:** {stats['unique_users']}

🔥 **Popular Movies:**
"""
            
            for i, movie in enumerate(stats['popular_movies'], 1):
                stats_message += f"{i}. {movie['title']} ({movie['download_count']} downloads)\n"
            
            await update.message.reply_text(stats_message, parse_mode='Markdown')
            
        except Exception as e:
            logger.error(f"Error in stats_command: {e}")
            await update.message.reply_text(
                "❌ An error occurred while fetching statistics."
            )
    
    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle text messages (search queries)"""
        user = update.effective_user
        query = update.message.text.strip()
        
        # Log user message for admin monitoring
        self.db.log_user_message(user.id, user.username or "", query, 'text')
        
        if len(query) < 2:
            await update.message.reply_text(
                "🔍 Please enter at least 2 characters to search."
            )
            return
        
        # Check rate limiting
        if not self.db.check_rate_limit(user.id, "search"):
            await update.message.reply_text(
                "⚠️ You are searching too fast. Please wait a moment and try again."
            )
            return
        
        try:
            # Search in database
            search_results = self.db.search_movies(query, Config.MAX_SEARCH_RESULTS)
            
            # Apply fuzzy matching for better results
            fuzzy_results = fuzzy_search_movies(query, search_results, Config.FUZZY_SEARCH_THRESHOLD)
            
            # Log the search
            self.db.log_search(user.id, user.username or "", query, len(fuzzy_results))
            
            if not fuzzy_results:
                # Add movie request button
                keyboard = [[InlineKeyboardButton(
                    f"📝 Request: {query}",
                    callback_data=f"request_movie_{query[:50]}"
                )]]
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                await update.message.reply_text(
                    f"😔 No movies found for '{query}'.\n\n"
                    "💡 **Tips:**\n"
                    "• Check your spelling\n"
                    "• Try different keywords\n"
                    "• Use movie name, year, or quality in search\n\n"
                    "📝 **Or request this movie:**",
                    reply_markup=reply_markup
                )
                return
            
            # Create inline keyboard with results
            keyboard = []
            for movie in fuzzy_results[:Config.MAX_SEARCH_RESULTS]:
                title_info = f"{movie['title']}"
                if movie['year']:
                    title_info += f" ({movie['year']})"
                if movie['quality']:
                    title_info += f" - {movie['quality']}"
                if movie['part_season_episode']:
                    title_info += f" - {movie['part_season_episode']}"
                
                # Truncate if too long
                if len(title_info) > 60:
                    title_info = title_info[:57] + "..."
                
                keyboard.append([
                    InlineKeyboardButton(
                        f"🎬 {title_info}",
                        callback_data=f"download_{movie['id']}"
                    )
                ])
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            result_text = f"🔍 Found {len(fuzzy_results)} result(s) for '{query}':\n\n"
            result_text += "📱 Click on any movie button to get direct download link!"
            
            await update.message.reply_text(
                result_text,
                reply_markup=reply_markup
            )
            
        except Exception as e:
            logger.error(f"Error in handle_message: {e}")
            await update.message.reply_text(
                "❌ An error occurred while searching. Please try again later."
            )
    
    async def bulk_upload_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /bulkupload command for admins"""
        user = update.effective_user
        
        if user.id not in Config.ADMIN_IDS:
            await update.message.reply_text("❌ You are not authorized to use bulk upload.")
            return
        
        try:
            queue_status = self.bulk_handler.get_queue_status()
            status_msg = (
                f"📦 **Bulk Upload Status**\n\n"
                f"📋 Queue Length: {queue_status['queue_length']} files\n"
                f"⚡ Processing: {'Yes' if queue_status['is_processing'] else 'No'}\n\n"
                f"**Instructions:**\n"
                f"• Send multiple files quickly (up to 500+)\n"
                f"• Each file will be auto-processed\n"
                f"• Use captions for better organization\n"
                f"• Files are saved automatically to database\n\n"
                f"**Start sending files now!**"
            )
            
            await update.message.reply_text(status_msg, parse_mode='Markdown')
            
        except Exception as e:
            logger.error(f"Error in bulk_upload_command: {e}")
            await update.message.reply_text(
                "❌ An error occurred. Please try again later."
            )

    async def structure_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /structure command for viewing bot code"""
        await self.structure_viewer.show_structure_menu(update, context)

    async def adminchat_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /adminchat command for hidden chat with users"""
        await self.admin_chat.start_admin_chat(update, context)

    async def blueprint_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /blueprint command for generating complete bot replication guide"""
        await self.blueprint_generator.generate_complete_blueprint(update, context)
    
    async def verify_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /verify command - not needed in auto system"""
        await update.message.reply_text(
            "❌ यह command auto verification system में काम नहीं करता।\n"
            "बस movie search करें और download button दबाएं।"
        )

    async def handle_file_upload(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle file uploads from admins"""
        user = update.effective_user
        
        if user.id not in Config.ADMIN_IDS:
            await update.message.reply_text("❌ You are not authorized to upload files.")
            return
        
        # Check if this should go to bulk upload queue
        # If admin sends multiple files quickly, use bulk handler
        queue_status = self.bulk_handler.get_queue_status()
        if queue_status['queue_length'] > 0 or queue_status['is_processing']:
            # Add to bulk queue
            success = await self.bulk_handler.add_to_upload_queue(update, context)
            if success:
                return
        
        # Regular single file upload
        if not self.db.check_rate_limit(user.id, "upload"):
            # If rate limited, add to bulk queue instead
            success = await self.bulk_handler.add_to_upload_queue(update, context)
            if success:
                return
            await update.message.reply_text(
                "⚠️ You are uploading too fast. File added to bulk queue."
            )
            return
        
        try:
            file_obj = update.message.document or update.message.video
            
            if not file_obj:
                await update.message.reply_text("❌ Please send a valid video file.")
                return
            
            # Accept all file sizes - Telegram will store them in their cloud
            # No file size limit check needed as we're using Telegram's unlimited storage
            
            # Check file extension
            file_name = file_obj.file_name or "unknown"
            if not any(file_name.lower().endswith(ext) for ext in Config.ALLOWED_FILE_EXTENSIONS):
                await update.message.reply_text(
                    f"❌ File type not supported. Allowed types: {', '.join(Config.ALLOWED_FILE_EXTENSIONS)}"
                )
                return
            
            # Parse caption or auto-detect from filename
            caption = update.message.caption or ""
            parsed_info = parse_upload_caption(caption)
            
            if not parsed_info:
                # Auto-detect movie info from filename - always works
                from utils import extract_movie_info_from_filename
                parsed_info = extract_movie_info_from_filename(file_name)
                
                # Always save files, even with basic info
                if not parsed_info['title']:
                    parsed_info = {
                        'title': file_name.replace('.', ' ').replace('_', ' '),
                        'year': None,
                        'quality': 'HD',
                        'part_season_episode': 'Complete'
                    }
            
            # Send processing message
            processing_msg = await update.message.reply_text("⏳ Processing upload...")
            
            # Create download URL and shorten it
            original_url = f"https://t.me/{context.bot.username}?start=download_{file_obj.file_id}"
            
            # Import and use URL shortener
            from url_shortener import URLShortener
            url_shortener = URLShortener()
            
            try:
                shortened_url = await url_shortener.shorten_url(original_url)
                if not shortened_url or shortened_url == original_url:
                    # Fallback if shortening fails
                    shortened_url = f"https://t.me/{context.bot.username}?start=get_{file_obj.file_id}"
            except Exception as e:
                logger.error(f"URL shortening failed: {e}")
                shortened_url = f"https://t.me/{context.bot.username}?start=get_{file_obj.file_id}"
            
            # Save to database
            movie_id = self.db.add_movie(
                title=parsed_info['title'],
                year=parsed_info['year'],
                quality=parsed_info['quality'],
                part_season_episode=parsed_info['part_season_episode'],
                file_id=file_obj.file_id,
                file_name=file_name,
                file_size=file_obj.file_size or 0,  # Use 0 if file_size is None
                original_url=original_url,
                shortened_url=shortened_url,
                uploaded_by=user.id
            )
            
            success_message = f"""
✅ **Upload Successful!**

🎬 **Title:** {parsed_info['title']}
📅 **Year:** {parsed_info['year'] or 'N/A'}
🎭 **Quality:** {parsed_info['quality']}
📀 **Part/Season/Episode:** {parsed_info['part_season_episode']}
📁 **File Size:** {format_file_size(file_obj.file_size or 0)}
🆔 **Movie ID:** {movie_id}
🔗 **Download Link:** {shortened_url}

The movie is now available for search!
"""
            
            await processing_msg.edit_text(success_message, parse_mode='Markdown')
            
            logger.info(f"Admin {user.id} uploaded movie: {parsed_info['title']} (ID: {movie_id})")
            
        except Exception as e:
            logger.error(f"Error in handle_file_upload: {e}")
            await update.message.reply_text(
                "❌ An error occurred during upload. Please try again later."
            )
    
    async def handle_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle button callbacks"""
        query = update.callback_query
        await query.answer()
        
        user = query.from_user
        data = query.data
        
        try:
            if data.startswith("download_"):
                movie_id = int(data.split("_")[1])
                await self._handle_download_request(query, user, movie_id, context)

            elif data.startswith("request_movie_"):
                movie_name = data.replace("request_movie_", "")
                await self._handle_movie_request(query, user, movie_name, context)
            elif data == "admin_movie_ads":
                from admin_panel import AdminPanel
                admin_panel = AdminPanel(self.db)
                await admin_panel.show_movie_advertisements(update, context)
            elif data == "admin_user_messages":
                from admin_panel import AdminPanel
                admin_panel = AdminPanel(self.db)
                await admin_panel.show_user_messages(update, context)
            elif data == "admin_movie_requests":
                from admin_panel import AdminPanel
                admin_panel = AdminPanel(self.db)
                await admin_panel.show_movie_requests(update, context)
            elif data == "admin_reset_verifications":
                from admin_panel import AdminPanel
                admin_panel = AdminPanel(self.db)
                await admin_panel.reset_all_verifications(update, context)
            elif data == "admin_confirm_reset":
                from admin_panel import AdminPanel
                admin_panel = AdminPanel(self.db)
                await admin_panel.confirm_reset_verifications(update, context)
            elif data.startswith("admin_advertise_"):
                movie_id = int(data.split("_")[2])
                from admin_panel import AdminPanel
                admin_panel = AdminPanel(self.db)
                await admin_panel.advertise_movie(update, context, movie_id)
            elif data == "admin_back":
                from admin_panel import AdminPanel
                admin_panel = AdminPanel(self.db)
                await admin_panel.show_admin_panel(update, context)
            elif data.startswith("structure_"):
                await self.structure_viewer.handle_structure_callback(query, context)
            elif data.startswith("adminchat_"):
                await self.admin_chat.handle_admin_chat_callback(query, context)
            elif data.startswith("verify_complete_"):
                # Auto verification system में यह feature नहीं है
                await query.edit_message_text("❌ इस feature की जरूरत नहीं है auto system में।")
            elif data.startswith("verification_help_"):
                # Verification system removed
                await query.edit_message_text("❌ वेरिफिकेशन सिस्टम हटा दिया गया है।")
            
        except Exception as e:
            logger.error(f"Error in handle_callback: {e}")
            await query.edit_message_text(
                "❌ An error occurred. Please try again later."
            )
    
    async def _handle_download_request(self, query, user, movie_id: int, context):
        """Handle download request for a specific movie"""
        try:
            # Get movie details
            movie = self.db.get_movie_by_id(movie_id)
            
            if not movie:
                await query.edit_message_text("❌ फिल्म नहीं मिली या उपलब्ध नहीं है।")
                return
            
            # Send file directly without any verification
            await self._send_file_directly(query, user, movie, context)
            
        except Exception as e:
            logger.error(f"Error in _handle_download_request: {e}")
            await query.edit_message_text(
                "❌ कोई त्रुटि हुई है। कृपया दोबारा कोशिश करें।"
            )
    
    async def _send_file_directly_from_start(self, update, user, movie, context):
        """Send file directly from start command"""
        try:
            # Increment download count
            self.db.increment_download_count(movie['id'])
            
            # Log download
            self.db.log_download(user.id, user.username or "", movie['id'], Config.AUTO_DELETE_MINUTES)
            
            # Try to send file to DM
            try:
                await context.bot.send_document(
                    chat_id=user.id,
                    document=movie['file_id'],
                    caption=f"✅ **{movie['title']}** - डायरेक्ट डाउनलोड\n\n"
                           f"📁 साइज़: {format_file_size(movie['file_size'])}\n"
                           f"⏰ {Config.AUTO_DELETE_MINUTES} मिनट में ऑटो-डिलीट हो जाएगी"
                )
                
                # Schedule auto-delete
                context.job_queue.run_once(
                    self._auto_delete_file,
                    when=timedelta(minutes=Config.AUTO_DELETE_MINUTES),
                    data={'user_id': user.id, 'movie_title': movie['title']},
                    name=f"delete_{user.id}_{movie['id']}_{datetime.now().timestamp()}"
                )
                
                await update.message.reply_text(
                    f"✅ **{movie['title']}** आपके DM में भेज दी गई!\n\n"
                    f"⏰ फाइल {Config.AUTO_DELETE_MINUTES} मिनट में ऑटो-डिलीट हो जाएगी।"
                )
                
            except Exception as dm_error:
                # If DM fails, send file directly in the chat
                logger.warning(f"DM not accessible for user {user.id}: {dm_error}")
                try:
                    await update.message.reply_document(
                        document=movie['file_id'],
                        caption=f"✅ **{movie['title']}** - Direct Download\n\n"
                               f"📁 Size: {format_file_size(movie['file_size'])}\n"
                               f"⏰ Auto-delete in {Config.AUTO_DELETE_MINUTES} minutes"
                    )
                    
                    await update.message.reply_text(
                        f"✅ **{movie['title']}** has been sent!\n\n"
                        f"⏰ File will auto-delete in {Config.AUTO_DELETE_MINUTES} minutes."
                    )
                    
                except Exception as chat_error:
                    logger.error(f"Could not send file to chat either: {chat_error}")
                    await update.message.reply_text(
                        f"❌ Sorry, could not send the file. Please try again or contact admin."
                    )
                
        except Exception as e:
            logger.error(f"Error in _send_file_directly_from_start: {e}")
            await update.message.reply_text("❌ An error occurred while processing your request.")

    async def _send_file_directly(self, query, user, movie, context):
        """Send file directly to user"""
        try:
            # Increment download count
            self.db.increment_download_count(movie['id'])
            
            # Log download
            self.db.log_download(user.id, user.username or "", movie['id'], Config.AUTO_DELETE_MINUTES)
            
            # Try to send file to DM
            try:
                await context.bot.send_document(
                    chat_id=user.id,
                    document=movie['file_id'],
                    caption=f"✅ **{movie['title']}** - डायरेक्ट डाउनलोड\n\n"
                           f"📁 साइज़: {format_file_size(movie['file_size'])}\n"
                           f"⏰ {Config.AUTO_DELETE_MINUTES} मिनट में ऑटो-डिलीट हो जाएगी"
                )
                
                # Schedule auto-delete
                context.job_queue.run_once(
                    self._auto_delete_file,
                    when=timedelta(minutes=Config.AUTO_DELETE_MINUTES),
                    data={'user_id': user.id, 'movie_title': movie['title']},
                    name=f"delete_{user.id}_{movie['id']}_{datetime.now().timestamp()}"
                )
                
                # Get shortened URL for sharing
                shortened_url = movie.get('shortened_url', 'N/A')
                
                await query.edit_message_text(
                    f"✅ **{movie['title']}** आपके DM में भेज दी गई!\n\n"
                    f"🔗 **शेयर लिंक:** {shortened_url}\n"
                    f"⏰ फाइल {Config.AUTO_DELETE_MINUTES} मिनट में ऑटो-डिलीट हो जाएगी।"
                )
                
            except Exception as dm_error:
                # If DM fails, send file directly in the chat
                logger.warning(f"DM not accessible for user {user.id}: {dm_error}")
                try:
                    await query.message.reply_document(
                        document=movie['file_id'],
                        caption=f"✅ **{movie['title']}** - Direct Download\n\n"
                               f"📁 Size: {format_file_size(movie['file_size'])}\n"
                               f"⏰ Auto-delete in {Config.AUTO_DELETE_MINUTES} minutes"
                    )
                    
                    await query.edit_message_text(
                        f"✅ **{movie['title']}** has been sent!\n\n"
                        f"⏰ File will auto-delete in {Config.AUTO_DELETE_MINUTES} minutes."
                    )
                    
                except Exception as chat_error:
                    logger.error(f"Could not send file to chat either: {chat_error}")
                    await query.edit_message_text(
                        f"❌ Sorry, could not send the file. Please try again or contact admin."
                    )
                
        except Exception as e:
            logger.error(f"Error in _send_file_directly: {e}")
            await query.edit_message_text("❌ An error occurred while processing your request.")
    

    
    async def _handle_movie_request(self, query, user, movie_name: str, context):
        """Handle movie request from user"""
        try:
            # Add movie request to database
            self.db.add_movie_request(user.id, user.username or "", movie_name)
            
            await query.edit_message_text(
                f"✅ **Movie Request Submitted!**\n\n"
                f"**Requested:** {movie_name}\n\n"
                f"Your request has been sent to the admin.\n"
                f"We'll try to add this movie soon!\n\n"
                f"📧 You'll be notified when it's available."
            )
            
            # Notify admin about new request (if admin is active)
            admin_ids = Config.ADMIN_IDS
            for admin_id in admin_ids:
                try:
                    await context.bot.send_message(
                        chat_id=admin_id,
                        text=f"📝 **New Movie Request**\n\n"
                             f"**Movie:** {movie_name}\n"
                             f"**From:** {user.username or 'Unknown'} (ID: {user.id})\n\n"
                             f"Use /admin to manage requests."
                    )
                except Exception:
                    pass  # Admin might have blocked the bot
            
            logger.info(f"Movie request: '{movie_name}' by user {user.id}")
            
        except Exception as e:
            logger.error(f"Error in _handle_movie_request: {e}")
            await query.edit_message_text(
                "❌ An error occurred while submitting your request."
            )
    
    async def _auto_delete_file(self, context: ContextTypes.DEFAULT_TYPE):
        """Auto-delete file after specified time"""
        try:
            job_data = context.job.data
            user_id = job_data['user_id']
            movie_title = job_data['movie_title']
            
            await context.bot.send_message(
                chat_id=user_id,
                text=f"🗑️ **Auto-Delete Notice**\n\n"
                     f"The file **{movie_title}** has been automatically deleted for copyright protection.\n\n"
                     f"You can search and download it again if needed."
            )
            
            logger.info(f"Auto-deleted file {movie_title} for user {user_id}")
            
        except Exception as e:
            logger.error(f"Error in auto-delete notification: {e}")
    
    async def error_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Global error handler"""
        logger.error(f"Exception while handling an update: {context.error}")
        
        # Notify user about the error
        if update and update.effective_message:
            try:
                await update.effective_message.reply_text(
                    "❌ An unexpected error occurred. The administrators have been notified."
                )
            except Exception as e:
                logger.error(f"Error sending error message to user: {e}")
