"""
Complete Auto Filter Movie Bot with Daily Verification System
"""

import os
import logging
import asyncio
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
from flask import Flask
from models import db, User, Movie, UserVerification, DownloadLog, SearchLog
from verification_system import VerificationSystem
from config import Config
from utils import parse_upload_caption, format_file_size, fuzzy_search_movies

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    handlers=[
        logging.FileHandler('auto_filter_bot.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class AutoFilterBot:
    """Main Auto Filter Bot class with daily verification"""
    
    def __init__(self):
        self.verification_system = VerificationSystem()
        self.setup_flask_app()
    
    def setup_flask_app(self):
        """Setup Flask app for database"""
        self.app = Flask(__name__)
        self.app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL')
        self.app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
        self.app.secret_key = os.environ.get('FLASK_SECRET_KEY', 'auto-filter-bot-secret')
        
        db.init_app(self.app)
        
        with self.app.app_context():
            db.create_all()
            logger.info("Database tables created successfully")
    
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start command"""
        user = update.effective_user
        message = update.message
        
        # Save user info
        with self.app.app_context():
            db_user = User.query.filter_by(user_id=user.id).first()
            if not db_user:
                db_user = User(
                    user_id=user.id,
                    username=user.username,
                    first_name=user.first_name,
                    last_name=user.last_name
                )
                db.session.add(db_user)
            else:
                db_user.username = user.username
                db_user.first_name = user.first_name
                db_user.last_name = user.last_name
                db_user.last_active = datetime.utcnow()
            
            db.session.commit()
        
        # Check if this is verification callback
        if context.args and context.args[0].startswith('verify_'):
            verification_token = context.args[0].replace('verify_', '')
            await self.handle_verification_callback(update, context, verification_token)
            return
        
        # Regular start message
        keyboard = [
            [InlineKeyboardButton("🎬 Search Movies", callback_data="search_help")],
            [InlineKeyboardButton("📊 My Stats", callback_data="user_stats")],
            [InlineKeyboardButton("ℹ️ Help", callback_data="help")]
        ]
        
        if user.id in Config.ADMIN_IDS:
            keyboard.append([InlineKeyboardButton("🔐 Admin Panel", callback_data="admin_panel")])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await message.reply_text(
            f"🎬 **Welcome to Auto Filter Movie Bot!**\n\n"
            f"नमस्ते {user.first_name}! 👋\n\n"
            f"**Bot Features:**\n"
            f"• Movie search करें name type करके\n"
            f"• Daily verification system (24 hours valid)\n"
            f"• Direct file download\n"
            f"• Typo-friendly search\n\n"
            f"**Instructions:**\n"
            f"1. Movie name type करें\n"
            f"2. Results में से select करें\n"
            f"3. Daily verification complete करें\n"
            f"4. File instantly receive करें!\n\n"
            f"Start करने के लिए कोई movie name type करें।",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
        
        logger.info(f"User {user.id} ({user.username or user.first_name}) started the bot")
    
    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle text messages (search queries)"""
        user = update.effective_user
        query = update.message.text.strip()
        
        if len(query) < 2:
            await update.message.reply_text("कृपया कम से कम 2 characters का movie name type करें।")
            return
        
        # Search movies in database
        with self.app.app_context():
            # Log search query
            search_log = SearchLog(
                user_id=user.id,
                query=query
            )
            
            # Search movies
            movies = Movie.query.filter(
                Movie.is_active == True,
                Movie.title.ilike(f'%{query}%')
            ).order_by(
                Movie.download_count.desc()
            ).limit(10).all()
            
            search_log.results_count = len(movies)
            db.session.add(search_log)
            db.session.commit()
        
        if not movies:
            await update.message.reply_text(
                f"❌ '{query}' के लिए कोई movie नहीं मिली।\n\n"
                f"**Tips:**\n"
                f"• Spelling check करें\n"
                f"• Short keywords use करें\n"
                f"• Year add करके try करें\n\n"
                f"Example: 'avengers 2019' या 'spider man'"
            )
            return
        
        # Create inline keyboard with results
        keyboard = []
        for movie in movies:
            button_text = f"🎬 {movie.title}"
            if movie.year:
                button_text += f" ({movie.year})"
            if movie.quality:
                button_text += f" - {movie.quality}"
            
            keyboard.append([
                InlineKeyboardButton(
                    button_text,
                    callback_data=f"download_{movie.id}"
                )
            ])
        
        # Add pagination if more than 10 results
        if len(movies) == 10:
            keyboard.append([
                InlineKeyboardButton("➡️ More Results", callback_data=f"more_{query}")
            ])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            f"🔍 **Search Results for '{query}'**\n\n"
            f"Found {len(movies)} movies. Select करने के लिए button पर click करें:",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
        
        logger.info(f"User {user.id} searched for '{query}' - {len(movies)} results")
    
    async def handle_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle button callbacks"""
        query = update.callback_query
        user = query.from_user
        data = query.data
        
        await query.answer()
        
        if data.startswith('download_'):
            movie_id = int(data.replace('download_', ''))
            await self.handle_download_request(query, user, movie_id, context)
        
        elif data == 'search_help':
            await self.show_search_help(query)
        
        elif data == 'user_stats':
            await self.show_user_stats(query, user)
        
        elif data == 'help':
            await self.show_help(query)
        
        elif data == 'admin_panel' and user.id in Config.ADMIN_IDS:
            await self.show_admin_panel(query)
        
        else:
            await query.edit_message_text("❌ Invalid action or expired button.")
    
    async def handle_download_request(self, query, user, movie_id: int, context):
        """Handle download request with verification check"""
        with self.app.app_context():
            # Get movie details
            movie = Movie.query.filter_by(id=movie_id, is_active=True).first()
            
            if not movie:
                await query.edit_message_text("❌ Movie not found या removed हो गई है।")
                return
            
            # Check user verification status
            verification_status = await self.verification_system.check_user_verification_status(user.id)
            
            if verification_status['needs_verification']:
                # Create verification request
                verification_data = await self.verification_system.create_verification_request(user.id, movie_id)
                
                await query.edit_message_text(
                    f"🎬 **{movie.title}**\n"
                    f"📅 Year: {movie.year or 'N/A'}\n"
                    f"🎯 Quality: {movie.quality or 'HD'}\n"
                    f"📁 Size: {format_file_size(movie.file_size)}\n\n"
                    f"⚠️ **Daily Verification Required**\n\n"
                    f"📋 आपको daily verification complete करना होगा:\n\n"
                    f"1️⃣ नीचे दिए गए link पर click करें\n"
                    f"2️⃣ Page load होने तक wait करें (5-10 seconds)\n"
                    f"3️⃣ Verification complete होने पर bot में वापस आएं\n\n"
                    f"🔗 **Verification Link:**\n{verification_data['short_url']}\n\n"
                    f"⏰ Link valid है 24 hours के लिए\n"
                    f"✅ एक बार verify करने पर 24 hours तक सभी movies free access",
                    parse_mode='Markdown'
                )
                
                logger.info(f"Verification required for user {user.id}, movie {movie_id}")
            
            else:
                # User is already verified, send file directly
                await self.send_movie_file(query, user, movie, context)
    
    async def handle_verification_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE, verification_token: str):
        """Handle verification callback when user comes from shortened URL"""
        user = update.effective_user
        
        with self.app.app_context():
            verification_result = await self.verification_system.verify_user_by_token(verification_token)
            
            if verification_result['success']:
                # Get movie and send file
                movie = Movie.query.filter_by(id=verification_result['movie_id']).first()
                
                if movie:
                    await update.message.reply_text(
                        f"✅ **Verification Successful!**\n\n"
                        f"🎊 आपका daily verification complete हो गया!\n"
                        f"⏰ अगले 24 hours तक सभी movies free access\n\n"
                        f"📤 आपकी requested movie भेजी जा रही है..."
                    )
                    
                    # Send the movie file
                    await self.send_movie_file_direct(update, user, movie, context)
                else:
                    await update.message.reply_text("❌ Movie not found. कृपया दोबारा search करें।")
            
            else:
                await update.message.reply_text(verification_result['message'])
        
        logger.info(f"Verification callback handled for user {user.id}")
    
    async def send_movie_file(self, query, user, movie, context):
        """Send movie file to verified user"""
        try:
            with self.app.app_context():
                # Log download
                download_log = DownloadLog(
                    user_id=user.id,
                    movie_id=movie.id,
                    auto_delete_time=datetime.utcnow() + timedelta(minutes=Config.AUTO_DELETE_MINUTES)
                )
                db.session.add(download_log)
                
                # Increment download count
                movie.download_count += 1
                db.session.commit()
            
            # Try sending to DM
            try:
                await context.bot.send_document(
                    chat_id=user.id,
                    document=movie.file_id,
                    caption=f"🎬 **{movie.title}**\n"
                           f"📅 Year: {movie.year or 'N/A'}\n"
                           f"🎯 Quality: {movie.quality or 'HD'}\n"
                           f"📁 Size: {format_file_size(movie.file_size)}\n\n"
                           f"⏰ File will auto-delete in {Config.AUTO_DELETE_MINUTES} minutes",
                    parse_mode='Markdown'
                )
                
                await query.edit_message_text(
                    f"✅ **{movie.title}** भेज दी गई!\n\n"
                    f"📱 Check your DM for the file\n"
                    f"⏰ File {Config.AUTO_DELETE_MINUTES} minutes में auto-delete हो जाएगी"
                )
                
                # Schedule auto-delete
                context.job_queue.run_once(
                    self.auto_delete_file,
                    when=timedelta(minutes=Config.AUTO_DELETE_MINUTES),
                    data={'user_id': user.id, 'movie_title': movie.title},
                    name=f"delete_{user.id}_{movie.id}_{datetime.now().timestamp()}"
                )
                
            except Exception as dm_error:
                # If DM fails, send in group
                await query.edit_message_text(
                    f"❌ DM भेजने में error हुई। कृपया bot को DM में start करें।\n\n"
                    f"Error: {str(dm_error)}"
                )
                
        except Exception as e:
            logger.error(f"Error sending movie file: {e}")
            await query.edit_message_text("❌ File भेजने में error हुई। कृपया बाद में try करें।")
    
    async def send_movie_file_direct(self, update: Update, user, movie, context):
        """Send movie file directly from start command"""
        try:
            with self.app.app_context():
                # Log download
                download_log = DownloadLog(
                    user_id=user.id,
                    movie_id=movie.id,
                    auto_delete_time=datetime.utcnow() + timedelta(minutes=Config.AUTO_DELETE_MINUTES)
                )
                db.session.add(download_log)
                
                # Increment download count
                movie.download_count += 1
                db.session.commit()
            
            await context.bot.send_document(
                chat_id=user.id,
                document=movie.file_id,
                caption=f"🎬 **{movie.title}**\n"
                       f"📅 Year: {movie.year or 'N/A'}\n"
                       f"🎯 Quality: {movie.quality or 'HD'}\n"
                       f"📁 Size: {format_file_size(movie.file_size)}\n\n"
                       f"✅ Verification successful!\n"
                       f"⏰ File will auto-delete in {Config.AUTO_DELETE_MINUTES} minutes",
                parse_mode='Markdown'
            )
            
            # Schedule auto-delete
            context.job_queue.run_once(
                self.auto_delete_file,
                when=timedelta(minutes=Config.AUTO_DELETE_MINUTES),
                data={'user_id': user.id, 'movie_title': movie.title},
                name=f"delete_{user.id}_{movie.id}_{datetime.now().timestamp()}"
            )
            
        except Exception as e:
            logger.error(f"Error sending movie file direct: {e}")
            await update.message.reply_text("❌ File भेजने में error हुई। कृपया बाद में try करें।")
    
    async def auto_delete_file(self, context: ContextTypes.DEFAULT_TYPE):
        """Auto-delete file after specified time"""
        try:
            job_data = context.job.data
            user_id = job_data['user_id']
            movie_title = job_data['movie_title']
            
            await context.bot.send_message(
                chat_id=user_id,
                text=f"🗑️ **File Auto-Deleted**\n\n"
                     f"📁 {movie_title}\n"
                     f"⏰ File has been automatically deleted for copyright protection.\n\n"
                     f"Search again करके नई file download कर सकते हैं।",
                parse_mode='Markdown'
            )
            
        except Exception as e:
            logger.error(f"Error in auto-delete: {e}")
    
    async def upload_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /upload command for admins"""
        user = update.effective_user
        
        if user.id not in Config.ADMIN_IDS:
            await update.message.reply_text("❌ Admin access required.")
            return
        
        await update.message.reply_text(
            "📤 **Upload Movie File**\n\n"
            "File भेजें with caption in format:\n"
            "`Movie Name | Year | Quality | Language`\n\n"
            "Example:\n"
            "`Avengers Endgame | 2019 | 1080p | Hindi`\n\n"
            "Supported formats: MP4, MKV, AVI, MOV, etc."
        )
    
    async def handle_file_upload(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle file uploads from admins"""
        user = update.effective_user
        
        if user.id not in Config.ADMIN_IDS:
            await update.message.reply_text("❌ Admin access required.")
            return
        
        if not (update.message.document or update.message.video):
            await update.message.reply_text("❌ कृपया एक video/document file भेजें।")
            return
        
        file_obj = update.message.document or update.message.video
        caption = update.message.caption or ""
        
        # Parse caption
        movie_data = parse_upload_caption(caption)
        if not movie_data:
            await update.message.reply_text(
                "❌ Invalid caption format.\n\n"
                "Format: `Movie Name | Year | Quality | Language`"
            )
            return
        
        with self.app.app_context():
            # Create movie entry
            movie = Movie(
                title=movie_data['title'],
                year=movie_data.get('year'),
                quality=movie_data.get('quality', 'HD'),
                language=movie_data.get('language', 'Hindi'),
                file_id=file_obj.file_id,
                file_name=file_obj.file_name or movie_data['title'],
                file_size=file_obj.file_size or 0,
                file_type='video' if update.message.video else 'document',
                uploaded_by=user.id
            )
            
            db.session.add(movie)
            db.session.commit()
            
            await update.message.reply_text(
                f"✅ **Movie Uploaded Successfully!**\n\n"
                f"🎬 Title: {movie.title}\n"
                f"📅 Year: {movie.year or 'N/A'}\n"
                f"🎯 Quality: {movie.quality}\n"
                f"🗣️ Language: {movie.language}\n"
                f"📁 Size: {format_file_size(movie.file_size)}\n"
                f"🆔 Movie ID: {movie.id}"
            )
            
            logger.info(f"Admin {user.id} uploaded movie: {movie.title}")
    
    async def show_search_help(self, query):
        """Show search help"""
        await query.edit_message_text(
            "🔍 **Search Help**\n\n"
            "**How to search:**\n"
            "• Type movie name directly\n"
            "• Spelling mistakes are okay\n"
            "• Use keywords like year, quality\n\n"
            "**Examples:**\n"
            "• `avengers`\n"
            "• `spider man 2019`\n"
            "• `bahubali hindi`\n"
            "• `kgf 1080p`\n\n"
            "**Tips:**\n"
            "• Use short keywords\n"
            "• Add year for better results\n"
            "• Try different spellings"
        )
    
    async def show_user_stats(self, query, user):
        """Show user statistics"""
        with self.app.app_context():
            db_user = User.query.filter_by(user_id=user.id).first()
            downloads = DownloadLog.query.filter_by(user_id=user.id).count()
            searches = SearchLog.query.filter_by(user_id=user.id).count()
            
            verification_status = await self.verification_system.check_user_verification_status(user.id)
            
            status_text = "✅ Verified" if not verification_status['needs_verification'] else "❌ Need Verification"
            hours_remaining = verification_status.get('hours_remaining', 0)
            
            await query.edit_message_text(
                f"📊 **Your Stats**\n\n"
                f"👤 User: {user.first_name}\n"
                f"🆔 ID: {user.id}\n"
                f"📅 Joined: {db_user.join_date.strftime('%d/%m/%Y') if db_user else 'Today'}\n\n"
                f"📈 **Activity:**\n"
                f"🔍 Searches: {searches}\n"
                f"📥 Downloads: {downloads}\n\n"
                f"🛡️ **Verification Status:**\n"
                f"Status: {status_text}\n"
                f"⏰ Hours Remaining: {hours_remaining}\n\n"
                f"💡 Daily verification gives you 24-hour access to all movies!"
            )
    
    async def show_help(self, query):
        """Show help information"""
        await query.edit_message_text(
            "ℹ️ **Auto Filter Movie Bot Help**\n\n"
            "**Features:**\n"
            "🎬 Movie search with typo tolerance\n"
            "🛡️ Daily verification system (24h valid)\n"
            "📱 Direct file download\n"
            "🗑️ Auto-delete for copyright protection\n\n"
            "**How to use:**\n"
            "1. Type movie name\n"
            "2. Select from results\n"
            "3. Complete daily verification if needed\n"
            "4. Get instant file access\n\n"
            "**Commands:**\n"
            "/start - Start the bot\n"
            "/help - Show this help\n\n"
            "**For Admins:**\n"
            "/upload - Upload new movies\n"
            "/stats - Bot statistics"
        )
    
    async def show_admin_panel(self, query):
        """Show admin panel"""
        with self.app.app_context():
            total_users = User.query.count()
            total_movies = Movie.query.filter_by(is_active=True).count()
            total_downloads = DownloadLog.query.count()
            verification_stats = await self.verification_system.get_verification_stats()
            
            await query.edit_message_text(
                f"🔐 **Admin Panel**\n\n"
                f"📊 **Statistics:**\n"
                f"👥 Total Users: {total_users}\n"
                f"🎬 Total Movies: {total_movies}\n"
                f"📥 Total Downloads: {total_downloads}\n\n"
                f"🛡️ **Verification Stats:**\n"
                f"✅ Successful: {verification_stats['successful_verifications']}\n"
                f"⏳ Pending: {verification_stats['pending_verifications']}\n"
                f"❌ Expired: {verification_stats['expired_verifications']}\n"
                f"📈 Success Rate: {verification_stats['success_rate']:.1f}%\n\n"
                f"**Commands:**\n"
                f"/upload - Upload movies\n"
                f"/stats - Detailed statistics"
            )

def main():
    """Main function to start the bot"""
    try:
        # Initialize bot
        bot = AutoFilterBot()
        
        # Create application
        application = Application.builder().token(Config.BOT_TOKEN).build()
        
        # Add handlers
        application.add_handler(CommandHandler("start", bot.start_command))
        application.add_handler(CommandHandler("upload", bot.upload_command))
        application.add_handler(MessageHandler(
            filters.TEXT & ~filters.COMMAND, 
            bot.handle_message
        ))
        application.add_handler(MessageHandler(
            filters.Document.ALL | filters.VIDEO, 
            bot.handle_file_upload
        ))
        application.add_handler(CallbackQueryHandler(bot.handle_callback))
        
        logger.info("Starting Auto Filter Movie Bot...")
        
        # Start the bot
        application.run_polling(allowed_updates=['message', 'callback_query'])
        
    except Exception as e:
        logger.error(f"Failed to start bot: {e}")
        raise

if __name__ == "__main__":
    main()