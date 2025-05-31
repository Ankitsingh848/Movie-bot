"""
Auto Filter Movie Bot with Daily Verification System
Based on Flask-SQLAlchemy with PostgreSQL
"""

import os
import logging
import asyncio
from datetime import datetime, timedelta
from flask import Flask
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes

# Setup logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    handlers=[
        logging.FileHandler('auto_filter_bot.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Initialize Flask app for database
app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.secret_key = os.environ.get('FLASK_SECRET_KEY', 'auto-filter-secret')

# Import database models after Flask setup
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import DeclarativeBase

class Base(DeclarativeBase):
    pass

db = SQLAlchemy(app, model_class=Base)

# Define models here
class User(db.Model):
    __tablename__ = 'users'
    
    user_id = db.Column(db.BigInteger, primary_key=True)
    username = db.Column(db.String(255), nullable=True)
    first_name = db.Column(db.String(255), nullable=True)
    join_date = db.Column(db.DateTime, default=datetime.utcnow)
    last_active = db.Column(db.DateTime, default=datetime.utcnow)
    last_verified = db.Column(db.DateTime, nullable=True)
    verification_count = db.Column(db.Integer, default=0)
    
    def is_verified_today(self):
        if not self.last_verified:
            return False
        return datetime.utcnow() - self.last_verified < timedelta(hours=24)
    
    def mark_verified(self):
        self.last_verified = datetime.utcnow()
        self.verification_count += 1

class Movie(db.Model):
    __tablename__ = 'movies'
    
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(500), nullable=False)
    year = db.Column(db.Integer, nullable=True)
    quality = db.Column(db.String(50), nullable=True)
    language = db.Column(db.String(50), default='Hindi')
    file_id = db.Column(db.String(200), unique=True, nullable=False)
    file_name = db.Column(db.String(500), nullable=False)
    file_size = db.Column(db.BigInteger, default=0)
    uploaded_by = db.Column(db.BigInteger, nullable=False)
    upload_date = db.Column(db.DateTime, default=datetime.utcnow)
    download_count = db.Column(db.Integer, default=0)
    is_active = db.Column(db.Boolean, default=True)

class UserVerification(db.Model):
    __tablename__ = 'user_verifications'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.BigInteger, nullable=False)
    movie_id = db.Column(db.Integer, nullable=False)
    verification_token = db.Column(db.String(100), unique=True, nullable=False)
    short_url = db.Column(db.String(500), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    expires_at = db.Column(db.DateTime, nullable=False)
    verified_at = db.Column(db.DateTime, nullable=True)
    is_verified = db.Column(db.Boolean, default=False)
    is_expired = db.Column(db.Boolean, default=False)
    
    @property
    def is_valid(self):
        return not self.is_expired and datetime.utcnow() < self.expires_at

class DownloadLog(db.Model):
    __tablename__ = 'download_logs'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.BigInteger, nullable=False)
    movie_id = db.Column(db.Integer, nullable=False)
    requested_at = db.Column(db.DateTime, default=datetime.utcnow)
    completed_at = db.Column(db.DateTime, nullable=True)
    auto_delete_time = db.Column(db.DateTime, nullable=True)
    is_deleted = db.Column(db.Boolean, default=False)

# Bot configuration
BOT_TOKEN = os.getenv("BOT_TOKEN", "")
BOT_USERNAME = os.getenv("BOT_USERNAME", "YourBotUsername")
ADMIN_IDS = [int(x.strip()) for x in os.getenv("ADMIN_IDS", "").split(",") if x.strip().isdigit()]
INSHORT_API_KEY = os.getenv("INSHORT_API_KEY", "")
AUTO_DELETE_MINUTES = 10

class AutoFilterBot:
    
    def __init__(self):
        # Create tables
        with app.app_context():
            db.create_all()
            logger.info("Database tables created")
    
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = update.effective_user
        
        with app.app_context():
            # Save user info
            db_user = User.query.filter_by(user_id=user.id).first()
            if not db_user:
                db_user = User(
                    user_id=user.id,
                    username=user.username,
                    first_name=user.first_name
                )
                db.session.add(db_user)
            else:
                db_user.username = user.username
                db_user.first_name = user.first_name
                db_user.last_active = datetime.utcnow()
            
            db.session.commit()
        
        # Check for verification callback
        if context.args and context.args[0].startswith('verify_'):
            verification_token = context.args[0].replace('verify_', '')
            await self.handle_verification(update, verification_token)
            return
        
        # Show welcome message
        keyboard = [
            [InlineKeyboardButton("🔍 Search Movies", callback_data="search_help")],
            [InlineKeyboardButton("📊 My Stats", callback_data="user_stats")],
        ]
        
        if user.id in ADMIN_IDS:
            keyboard.append([InlineKeyboardButton("🔐 Admin Panel", callback_data="admin_panel")])
        
        await update.message.reply_text(
            f"🎬 **Welcome to Auto Filter Movie Bot!**\n\n"
            f"नमस्ते {user.first_name}! 👋\n\n"
            f"**Features:**\n"
            f"• Daily verification system (24 hours valid)\n"
            f"• Movie search with typo tolerance\n"
            f"• Direct file download\n"
            f"• Auto-delete for copyright protection\n\n"
            f"**How to use:**\n"
            f"1. Type movie name to search\n"
            f"2. Select from results\n"
            f"3. Complete daily verification (once per day)\n"
            f"4. Get instant file access!\n\n"
            f"Start करने के लिए movie name type करें।",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
    
    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = update.effective_user
        query = update.message.text.strip()
        
        if len(query) < 2:
            await update.message.reply_text("कृपया कम से कम 2 characters का movie name type करें।")
            return
        
        with app.app_context():
            # Search movies
            movies = Movie.query.filter(
                Movie.is_active == True,
                Movie.title.ilike(f'%{query}%')
            ).order_by(Movie.download_count.desc()).limit(10).all()
        
        if not movies:
            await update.message.reply_text(
                f"❌ '{query}' के लिए कोई movie नहीं मिली।\n\n"
                f"**Tips:**\n"
                f"• Spelling check करें\n"
                f"• Short keywords use करें\n"
                f"• Year add करके try करें"
            )
            return
        
        # Create results keyboard
        keyboard = []
        for movie in movies:
            button_text = f"🎬 {movie.title}"
            if movie.year:
                button_text += f" ({movie.year})"
            if movie.quality:
                button_text += f" - {movie.quality}"
            
            keyboard.append([
                InlineKeyboardButton(button_text, callback_data=f"download_{movie.id}")
            ])
        
        await update.message.reply_text(
            f"🔍 **Search Results for '{query}'**\n\n"
            f"Found {len(movies)} movies:",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
    
    async def handle_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        user = query.from_user
        data = query.data
        
        await query.answer()
        
        if data.startswith('download_'):
            movie_id = int(data.replace('download_', ''))
            await self.handle_download_request(query, user, movie_id, context)
        
        elif data == 'search_help':
            await query.edit_message_text(
                "🔍 **Search Help**\n\n"
                "Simply type the movie name and I'll find it for you!\n\n"
                "Examples:\n"
                "• avengers\n"
                "• spider man\n"
                "• kgf hindi\n\n"
                "Spelling mistakes are okay!"
            )
        
        elif data == 'user_stats':
            await self.show_user_stats(query, user)
    
    async def handle_download_request(self, query, user, movie_id: int, context):
        with app.app_context():
            movie = Movie.query.filter_by(id=movie_id, is_active=True).first()
            if not movie:
                await query.edit_message_text("❌ Movie not found.")
                return
            
            # Check verification status
            db_user = User.query.filter_by(user_id=user.id).first()
            
            if db_user and db_user.is_verified_today():
                # User is verified, send file directly
                await self.send_movie_file(query, user, movie, context)
            else:
                # Need verification
                await self.request_verification(query, user, movie, context)
    
    async def request_verification(self, query, user, movie, context):
        import hashlib
        import uuid
        
        with app.app_context():
            # Generate verification token
            timestamp = datetime.utcnow().timestamp()
            unique_string = f"{user.id}_{movie.id}_{timestamp}_{uuid.uuid4().hex[:8]}"
            verification_token = hashlib.md5(unique_string.encode()).hexdigest()
            
            # Create short URL (using InShort API if available)
            original_url = f"https://t.me/{BOT_USERNAME}?start=verify_{verification_token}"
            short_url = await self.create_short_url(original_url)
            
            # Save verification request
            verification = UserVerification(
                user_id=user.id,
                movie_id=movie.id,
                verification_token=verification_token,
                short_url=short_url,
                expires_at=datetime.utcnow() + timedelta(hours=24)
            )
            db.session.add(verification)
            db.session.commit()
        
        await query.edit_message_text(
            f"🎬 **{movie.title}**\n"
            f"📅 Year: {movie.year or 'N/A'}\n"
            f"🎯 Quality: {movie.quality or 'HD'}\n"
            f"📁 Size: {self.format_file_size(movie.file_size)}\n\n"
            f"⚠️ **Daily Verification Required**\n\n"
            f"आपको daily verification complete करना होगा:\n\n"
            f"1️⃣ नीचे दिए गए link पर click करें\n"
            f"2️⃣ Page load होने तक wait करें\n"
            f"3️⃣ Bot में वापस आएं\n\n"
            f"🔗 **Verification Link:**\n{short_url}\n\n"
            f"⏰ Valid for 24 hours\n"
            f"✅ एक बार verify करने पर 24 hours free access",
            parse_mode='Markdown'
        )
    
    async def create_short_url(self, original_url):
        """Create shortened URL using InShort API"""
        if not INSHORT_API_KEY:
            return original_url
        
        try:
            import aiohttp
            async with aiohttp.ClientSession() as session:
                data = {
                    'url': original_url,
                    'api': INSHORT_API_KEY
                }
                async with session.post("https://inshorturl.com/api", data=data) as response:
                    if response.status == 200:
                        result = await response.json()
                        if result.get('status') == 'success':
                            return result.get('shortenedUrl', original_url)
            return original_url
        except Exception as e:
            logger.error(f"URL shortening failed: {e}")
            return original_url
    
    async def handle_verification(self, update: Update, verification_token: str):
        user = update.effective_user
        
        with app.app_context():
            verification = UserVerification.query.filter_by(
                verification_token=verification_token,
                is_verified=False
            ).first()
            
            if not verification:
                await update.message.reply_text("❌ Invalid या expired verification link.")
                return
            
            if not verification.is_valid:
                verification.is_expired = True
                db.session.commit()
                await update.message.reply_text("❌ Verification link expired. नया link generate करें।")
                return
            
            # Mark as verified
            verification.is_verified = True
            verification.verified_at = datetime.utcnow()
            
            # Update user verification
            db_user = User.query.filter_by(user_id=user.id).first()
            if db_user:
                db_user.mark_verified()
            
            db.session.commit()
            
            # Get movie and send file
            movie = Movie.query.filter_by(id=verification.movie_id).first()
            if movie:
                await update.message.reply_text(
                    f"✅ **Verification Successful!**\n\n"
                    f"🎊 Daily verification complete!\n"
                    f"⏰ 24 hours free access\n\n"
                    f"📤 Sending your movie..."
                )
                
                await self.send_movie_file_direct(update, user, movie)
            else:
                await update.message.reply_text("❌ Movie not found.")
    
    async def send_movie_file(self, query, user, movie, context):
        try:
            with app.app_context():
                # Log download
                download_log = DownloadLog(
                    user_id=user.id,
                    movie_id=movie.id,
                    auto_delete_time=datetime.utcnow() + timedelta(minutes=AUTO_DELETE_MINUTES)
                )
                db.session.add(download_log)
                
                movie.download_count += 1
                db.session.commit()
            
            # Send file to DM
            await context.bot.send_document(
                chat_id=user.id,
                document=movie.file_id,
                caption=f"🎬 **{movie.title}**\n"
                       f"📅 Year: {movie.year or 'N/A'}\n"
                       f"🎯 Quality: {movie.quality or 'HD'}\n"
                       f"📁 Size: {self.format_file_size(movie.file_size)}\n\n"
                       f"⏰ Auto-delete in {AUTO_DELETE_MINUTES} minutes",
                parse_mode='Markdown'
            )
            
            await query.edit_message_text(
                f"✅ **{movie.title}** sent successfully!\n\n"
                f"📱 Check your DM\n"
                f"⏰ File will auto-delete in {AUTO_DELETE_MINUTES} minutes"
            )
            
            # Schedule auto-delete
            context.job_queue.run_once(
                self.auto_delete_file,
                when=timedelta(minutes=AUTO_DELETE_MINUTES),
                data={'user_id': user.id, 'movie_title': movie.title}
            )
            
        except Exception as e:
            logger.error(f"Error sending file: {e}")
            await query.edit_message_text("❌ Error sending file. Please try again.")
    
    async def send_movie_file_direct(self, update: Update, user, movie):
        try:
            with app.app_context():
                download_log = DownloadLog(
                    user_id=user.id,
                    movie_id=movie.id,
                    auto_delete_time=datetime.utcnow() + timedelta(minutes=AUTO_DELETE_MINUTES)
                )
                db.session.add(download_log)
                movie.download_count += 1
                db.session.commit()
            
            await update.message.reply_document(
                document=movie.file_id,
                caption=f"🎬 **{movie.title}**\n"
                       f"✅ Verification successful!\n"
                       f"⏰ Auto-delete in {AUTO_DELETE_MINUTES} minutes",
                parse_mode='Markdown'
            )
            
        except Exception as e:
            logger.error(f"Error sending file direct: {e}")
            await update.message.reply_text("❌ Error sending file.")
    
    async def auto_delete_file(self, context: ContextTypes.DEFAULT_TYPE):
        try:
            job_data = context.job.data
            await context.bot.send_message(
                chat_id=job_data['user_id'],
                text=f"🗑️ File auto-deleted: {job_data['movie_title']}"
            )
        except Exception as e:
            logger.error(f"Auto-delete error: {e}")
    
    async def upload_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if update.effective_user.id not in ADMIN_IDS:
            await update.message.reply_text("❌ Admin access required.")
            return
        
        await update.message.reply_text(
            "📤 **Upload Movie**\n\n"
            "Send file with caption:\n"
            "`Movie Name | Year | Quality | Language`\n\n"
            "Example:\n"
            "`Avengers Endgame | 2019 | 1080p | Hindi`"
        )
    
    async def handle_file_upload(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if update.effective_user.id not in ADMIN_IDS:
            return
        
        file_obj = update.message.document or update.message.video
        if not file_obj:
            return
        
        caption = update.message.caption or ""
        parts = [part.strip() for part in caption.split('|')]
        
        if len(parts) < 2:
            await update.message.reply_text("❌ Invalid caption format.")
            return
        
        with app.app_context():
            movie = Movie(
                title=parts[0],
                year=int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else None,
                quality=parts[2] if len(parts) > 2 else 'HD',
                language=parts[3] if len(parts) > 3 else 'Hindi',
                file_id=file_obj.file_id,
                file_name=file_obj.file_name or parts[0],
                file_size=file_obj.file_size or 0,
                uploaded_by=update.effective_user.id
            )
            db.session.add(movie)
            db.session.commit()
            
            await update.message.reply_text(
                f"✅ **Movie Uploaded!**\n\n"
                f"🎬 {movie.title}\n"
                f"🆔 ID: {movie.id}"
            )
    
    async def show_user_stats(self, query, user):
        with app.app_context():
            db_user = User.query.filter_by(user_id=user.id).first()
            downloads = DownloadLog.query.filter_by(user_id=user.id).count()
            
            verification_status = "✅ Verified" if db_user and db_user.is_verified_today() else "❌ Need Verification"
            
            await query.edit_message_text(
                f"📊 **Your Stats**\n\n"
                f"👤 Name: {user.first_name}\n"
                f"🆔 ID: {user.id}\n"
                f"📥 Downloads: {downloads}\n"
                f"🛡️ Status: {verification_status}\n\n"
                f"Daily verification gives 24-hour access!"
            )
    
    def format_file_size(self, size_bytes):
        if size_bytes == 0:
            return "0 B"
        
        size_names = ["B", "KB", "MB", "GB"]
        i = 0
        size = float(size_bytes)
        
        while size >= 1024.0 and i < len(size_names) - 1:
            size /= 1024.0
            i += 1
        
        return f"{size:.1f} {size_names[i]}"

def main():
    """Start the auto filter bot"""
    try:
        if not BOT_TOKEN:
            raise ValueError("BOT_TOKEN is required")
        
        bot = AutoFilterBot()
        
        application = Application.builder().token(BOT_TOKEN).build()
        
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
        
        logger.info("Starting Auto Filter Movie Bot with Daily Verification...")
        application.run_polling(allowed_updates=['message', 'callback_query'])
        
    except Exception as e:
        logger.error(f"Failed to start bot: {e}")
        raise

if __name__ == "__main__":
    main()