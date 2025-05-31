import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from database import Database
from utils import format_file_size, format_duration
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

class AdminPanel:
    """Admin panel functionality for the bot"""
    
    def __init__(self, database: Database):
        self.db = database
    
    async def show_admin_panel(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show main admin panel"""
        try:
            stats = self.db.get_stats()
            
            admin_message = f"""
🔐 **Admin Control Panel**

📊 **Quick Stats:**
• Movies: {stats['total_movies']}
• Downloads: {stats['total_downloads']}  
• Searches: {stats['total_searches']}
• Users: {stats['unique_users']}

🎬 **Top Movies:**
"""
            
            for i, movie in enumerate(stats['popular_movies'][:3], 1):
                admin_message += f"{i}. {movie['title']} ({movie['download_count']} downloads)\n"
            
            keyboard = [
                [
                    InlineKeyboardButton("📊 Detailed Stats", callback_data="admin_detailed_stats"),
                    InlineKeyboardButton("🎬 Manage Movies", callback_data="admin_manage_movies")
                ],
                [
                    InlineKeyboardButton("📢 Movie Ads", callback_data="admin_movie_ads"),
                    InlineKeyboardButton("💬 User Messages", callback_data="admin_user_messages")
                ],
                [
                    InlineKeyboardButton("🎭 Movie Requests", callback_data="admin_movie_requests"),
                    InlineKeyboardButton("👥 User Analytics", callback_data="admin_user_analytics")
                ],
                [
                    InlineKeyboardButton("🔄 Reset Verifications", callback_data="admin_reset_verifications"),
                    InlineKeyboardButton("🧹 Cleanup", callback_data="admin_cleanup")
                ]
            ]
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(
                admin_message,
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )
            
        except Exception as e:
            logger.error(f"Error showing admin panel: {e}")
            await update.message.reply_text(
                "❌ Error loading admin panel. Please try again."
            )
    
    async def show_detailed_stats(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show detailed statistics"""
        try:
            stats = self.db.get_stats()
            
            # Get additional stats
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                
                # Today's activity
                cursor.execute("""
                    SELECT COUNT(*) as count FROM search_logs 
                    WHERE DATE(search_date) = DATE('now')
                """)
                today_searches = cursor.fetchone()['count']
                
                cursor.execute("""
                    SELECT COUNT(*) as count FROM download_logs 
                    WHERE DATE(download_date) = DATE('now')
                """)
                today_downloads = cursor.fetchone()['count']
                
                # Most active users
                cursor.execute("""
                    SELECT username, COUNT(*) as search_count 
                    FROM search_logs 
                    WHERE username IS NOT NULL 
                    GROUP BY user_id, username 
                    ORDER BY search_count DESC 
                    LIMIT 5
                """)
                active_users = cursor.fetchall()
                
                # Recent uploads
                cursor.execute("""
                    SELECT title, upload_date, download_count 
                    FROM movies 
                    WHERE is_active = 1 
                    ORDER BY upload_date DESC 
                    LIMIT 5
                """)
                recent_uploads = cursor.fetchall()
            
            detailed_message = f"""
📊 **Detailed Statistics**

**Overall:**
• Total Movies: {stats['total_movies']}
• Total Downloads: {stats['total_downloads']}
• Total Searches: {stats['total_searches']}
• Unique Users: {stats['unique_users']}

**Today's Activity:**
• Searches: {today_searches}
• Downloads: {today_downloads}

**Most Active Users:**
"""
            
            for i, user in enumerate(active_users, 1):
                username = user['username'] or 'Anonymous'
                detailed_message += f"{i}. @{username} ({user['search_count']} searches)\n"
            
            detailed_message += "\n**Recent Uploads:**\n"
            for upload in recent_uploads:
                upload_date = datetime.fromisoformat(upload['upload_date']).strftime('%m/%d %H:%M')
                detailed_message += f"• {upload['title']} - {upload_date} ({upload['download_count']} downloads)\n"
            
            keyboard = [[InlineKeyboardButton("🔙 Back to Admin Panel", callback_data="admin_back")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            if update.callback_query:
                await update.callback_query.edit_message_text(
                    detailed_message,
                    reply_markup=reply_markup,
                    parse_mode='Markdown'
                )
            else:
                await update.message.reply_text(
                    detailed_message,
                    reply_markup=reply_markup,
                    parse_mode='Markdown'
                )
                
        except Exception as e:
            logger.error(f"Error showing detailed stats: {e}")
            await update.effective_message.reply_text(
                "❌ Error loading detailed statistics."
            )
    
    async def show_movie_management(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show movie management interface"""
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                
                # Get movies with low downloads
                cursor.execute("""
                    SELECT id, title, download_count, upload_date, file_size 
                    FROM movies 
                    WHERE is_active = 1 
                    ORDER BY download_count ASC, upload_date DESC 
                    LIMIT 10
                """)
                low_downloads = cursor.fetchall()
                
                # Get movies with high downloads
                cursor.execute("""
                    SELECT id, title, download_count, upload_date, file_size 
                    FROM movies 
                    WHERE is_active = 1 
                    ORDER BY download_count DESC 
                    LIMIT 5
                """)
                popular_movies = cursor.fetchall()
            
            management_message = f"""
🎬 **Movie Management**

**Popular Movies:**
"""
            
            for movie in popular_movies:
                upload_date = datetime.fromisoformat(movie['upload_date']).strftime('%m/%d')
                size = format_file_size(movie['file_size'])
                management_message += f"• {movie['title']} ({movie['download_count']} downloads, {size}, {upload_date})\n"
            
            management_message += "\n**Low Activity Movies:**\n"
            for movie in low_downloads:
                upload_date = datetime.fromisoformat(movie['upload_date']).strftime('%m/%d')
                size = format_file_size(movie['file_size'])
                management_message += f"• {movie['title']} ({movie['download_count']} downloads, {size}, {upload_date})\n"
            
            keyboard = [
                [
                    InlineKeyboardButton("🗑️ Clean Low Activity", callback_data="admin_clean_low_activity"),
                    InlineKeyboardButton("📊 Export Data", callback_data="admin_export_data")
                ],
                [InlineKeyboardButton("🔙 Back", callback_data="admin_back")]
            ]
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.callback_query.edit_message_text(
                management_message,
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )
            
        except Exception as e:
            logger.error(f"Error showing movie management: {e}")
            await update.callback_query.answer("❌ Error loading movie management.")
    
    async def show_user_analytics(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show user analytics"""
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                
                # User activity over time
                cursor.execute("""
                    SELECT DATE(search_date) as date, COUNT(*) as searches 
                    FROM search_logs 
                    WHERE search_date >= DATE('now', '-7 days')
                    GROUP BY DATE(search_date) 
                    ORDER BY date DESC
                """)
                daily_activity = cursor.fetchall()
                
                # Popular search terms
                cursor.execute("""
                    SELECT search_query, COUNT(*) as count 
                    FROM search_logs 
                    WHERE search_date >= DATE('now', '-7 days')
                    GROUP BY LOWER(search_query) 
                    ORDER BY count DESC 
                    LIMIT 10
                """)
                popular_searches = cursor.fetchall()
                
                # New users (first search)
                cursor.execute("""
                    SELECT COUNT(DISTINCT user_id) as new_users 
                    FROM search_logs 
                    WHERE DATE(search_date) = DATE('now')
                    AND user_id NOT IN (
                        SELECT DISTINCT user_id 
                        FROM search_logs 
                        WHERE DATE(search_date) < DATE('now')
                    )
                """)
                new_users_today = cursor.fetchone()['new_users']
            
            analytics_message = f"""
👥 **User Analytics**

**New Users Today:** {new_users_today}

**Daily Activity (Last 7 Days):**
"""
            
            for activity in daily_activity:
                date_str = datetime.fromisoformat(activity['date']).strftime('%m/%d')
                analytics_message += f"• {date_str}: {activity['searches']} searches\n"
            
            analytics_message += "\n**Popular Searches (Last 7 Days):**\n"
            for i, search in enumerate(popular_searches[:5], 1):
                analytics_message += f"{i}. '{search['search_query']}' ({search['count']} times)\n"
            
            keyboard = [[InlineKeyboardButton("🔙 Back", callback_data="admin_back")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.callback_query.edit_message_text(
                analytics_message,
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )
            
        except Exception as e:
            logger.error(f"Error showing user analytics: {e}")
            await update.callback_query.answer("❌ Error loading user analytics.")
    
    async def show_cleanup_options(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show cleanup options"""
        try:
            from file_manager import FileManager
            
            file_manager = FileManager()
            temp_files = file_manager.list_temp_files()
            temp_size = file_manager.get_directory_size()
            
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                
                # Old logs
                cursor.execute("""
                    SELECT COUNT(*) as count FROM search_logs 
                    WHERE search_date < DATE('now', '-30 days')
                """)
                old_search_logs = cursor.fetchone()['count']
                
                cursor.execute("""
                    SELECT COUNT(*) as count FROM download_logs 
                    WHERE download_date < DATE('now', '-30 days')
                """)
                old_download_logs = cursor.fetchone()['count']
                
                # Inactive movies
                cursor.execute("""
                    SELECT COUNT(*) as count FROM movies 
                    WHERE is_active = 1 AND download_count = 0 
                    AND upload_date < DATE('now', '-7 days')
                """)
                inactive_movies = cursor.fetchone()['count']
            
            cleanup_message = f"""
🧹 **Cleanup Options**

**Temporary Files:**
• Count: {len(temp_files)}
• Size: {format_file_size(temp_size)}

**Old Logs:**
• Search Logs (>30 days): {old_search_logs}
• Download Logs (>30 days): {old_download_logs}

**Inactive Content:**
• Movies (0 downloads, >7 days): {inactive_movies}

**Actions Available:**
"""
            
            keyboard = [
                [
                    InlineKeyboardButton("🗑️ Clean Temp Files", callback_data="admin_clean_temp"),
                    InlineKeyboardButton("📋 Clean Old Logs", callback_data="admin_clean_logs")
                ],
                [
                    InlineKeyboardButton("🎬 Clean Inactive Movies", callback_data="admin_clean_inactive"),
                    InlineKeyboardButton("🧹 Full Cleanup", callback_data="admin_full_cleanup")
                ],
                [InlineKeyboardButton("🔙 Back", callback_data="admin_back")]
            ]
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.callback_query.edit_message_text(
                cleanup_message,
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )
            
        except Exception as e:
            logger.error(f"Error showing cleanup options: {e}")
            await update.callback_query.answer("❌ Error loading cleanup options.")
    
    async def perform_cleanup(self, update: Update, context: ContextTypes.DEFAULT_TYPE, cleanup_type: str):
        """Perform specific cleanup action"""
        try:
            results = {}
            
            if cleanup_type in ['temp', 'full']:
                from file_manager import FileManager
                file_manager = FileManager()
                deleted_files = file_manager.cleanup_old_files(max_age_hours=1)
                results['temp_files'] = deleted_files
            
            if cleanup_type in ['logs', 'full']:
                with self.db.get_connection() as conn:
                    cursor = conn.cursor()
                    
                    # Clean old search logs
                    cursor.execute("""
                        DELETE FROM search_logs 
                        WHERE search_date < DATE('now', '-30 days')
                    """)
                    search_logs_deleted = cursor.rowcount
                    
                    # Clean old download logs
                    cursor.execute("""
                        DELETE FROM download_logs 
                        WHERE download_date < DATE('now', '-30 days')
                        AND auto_delete_date IS NULL
                    """)
                    download_logs_deleted = cursor.rowcount
                    
                    conn.commit()
                    
                    results['search_logs'] = search_logs_deleted
                    results['download_logs'] = download_logs_deleted
            
            if cleanup_type in ['inactive', 'full']:
                with self.db.get_connection() as conn:
                    cursor = conn.cursor()
                    
                    # Mark inactive movies as inactive
                    cursor.execute("""
                        UPDATE movies 
                        SET is_active = 0 
                        WHERE is_active = 1 AND download_count = 0 
                        AND upload_date < DATE('now', '-7 days')
                    """)
                    inactive_movies = cursor.rowcount
                    conn.commit()
                    
                    results['inactive_movies'] = inactive_movies
            
            # Create results message
            results_message = "✅ **Cleanup Completed**\n\n"
            
            if 'temp_files' in results:
                results_message += f"🗑️ Temporary files deleted: {results['temp_files']}\n"
            if 'search_logs' in results:
                results_message += f"📋 Search logs cleaned: {results['search_logs']}\n"
            if 'download_logs' in results:
                results_message += f"📋 Download logs cleaned: {results['download_logs']}\n"
            if 'inactive_movies' in results:
                results_message += f"🎬 Movies marked inactive: {results['inactive_movies']}\n"
            
            keyboard = [[InlineKeyboardButton("🔙 Back to Cleanup", callback_data="admin_cleanup")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.callback_query.edit_message_text(
                results_message,
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )
            
            logger.info(f"Cleanup performed: {cleanup_type}, Results: {results}")
            
        except Exception as e:
            logger.error(f"Error performing cleanup {cleanup_type}: {e}")
            await update.callback_query.answer("❌ Error during cleanup operation.")
    
    async def show_movie_advertisements(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show movie advertisement options"""
        try:
            movies = []
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT id, title, year, quality, upload_date 
                    FROM movies WHERE is_active = 1 
                    ORDER BY upload_date DESC LIMIT 10
                """)
                movies = cursor.fetchall()
            
            ad_message = """
📢 **Movie Advertisement Panel**

Send advertisement to all users about new movies!

**Recently Added Movies:**
"""
            
            for i, movie in enumerate(movies[:5], 1):
                upload_date = datetime.fromisoformat(movie['upload_date']).strftime('%Y-%m-%d')
                ad_message += f"{i}. {movie['title']} ({movie['year']}) - {movie['quality']}\n"
            
            keyboard = []
            for movie in movies[:5]:
                keyboard.append([InlineKeyboardButton(
                    f"📢 Advertise: {movie['title'][:30]}...",
                    callback_data=f"admin_advertise_{movie['id']}"
                )])
            
            keyboard.append([InlineKeyboardButton("🔙 Back", callback_data="admin_back")])
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.callback_query.edit_message_text(
                ad_message,
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )
            
        except Exception as e:
            logger.error(f"Error showing movie advertisements: {e}")
            await update.callback_query.answer("❌ Error loading movie advertisements.")
    
    async def show_user_messages(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show recent user messages for monitoring"""
        try:
            messages = self.db.get_recent_user_messages(20)
            
            messages_text = """
💬 **User Messages Monitor**

**Recent user interactions:**

"""
            
            if not messages:
                messages_text += "No recent messages found."
            else:
                for msg in messages:
                    username = f"@{msg['username']}" if msg['username'] else f"User {msg['user_id']}"
                    date = datetime.fromisoformat(msg['message_date']).strftime('%m-%d %H:%M')
                    message_preview = msg['message_text'][:50] + "..." if len(msg['message_text']) > 50 else msg['message_text']
                    messages_text += f"• **{username}** ({date}): {message_preview}\n"
            
            keyboard = [
                [InlineKeyboardButton("🔄 Refresh", callback_data="admin_user_messages")],
                [InlineKeyboardButton("🔙 Back", callback_data="admin_back")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.callback_query.edit_message_text(
                messages_text,
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )
            
        except Exception as e:
            logger.error(f"Error showing user messages: {e}")
            await update.callback_query.answer("❌ Error loading user messages.")
    
    async def show_movie_requests(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show movie requests from users"""
        try:
            requests = self.db.get_movie_requests()
            
            requests_text = """
🎭 **Movie Requests**

**Pending user requests:**

"""
            
            if not requests:
                requests_text += "No pending movie requests."
            else:
                for req in requests:
                    username = req['username'] or 'Unknown'
                    date = datetime.fromisoformat(req['request_date']).strftime('%m-%d %H:%M')
                    requests_text += f"• **{req['movie_name']}** by {username} ({date})\n"
            
            keyboard = [
                [InlineKeyboardButton("🔄 Refresh", callback_data="admin_movie_requests")],
                [InlineKeyboardButton("🔙 Back", callback_data="admin_back")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.callback_query.edit_message_text(
                requests_text,
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )
            
        except Exception as e:
            logger.error(f"Error showing movie requests: {e}")
            await update.callback_query.answer("❌ Error loading movie requests.")
    
    async def reset_all_verifications(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Reset all user verifications"""
        try:
            # Show confirmation first
            keyboard = [
                [
                    InlineKeyboardButton("✅ Yes, Reset All", callback_data="admin_confirm_reset"),
                    InlineKeyboardButton("❌ Cancel", callback_data="admin_back")
                ]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.callback_query.edit_message_text(
                "⚠️ **Reset All Verifications**\n\n"
                "This will reset ALL user verifications!\n"
                "All users will need to complete verification again.\n\n"
                "Are you sure you want to continue?",
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )
            
        except Exception as e:
            logger.error(f"Error showing reset confirmation: {e}")
            await update.callback_query.answer("❌ Error showing reset confirmation.")
    
    async def confirm_reset_verifications(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Confirm and execute verification reset"""
        try:
            self.db.reset_all_verifications()
            
            keyboard = [[InlineKeyboardButton("🔙 Back", callback_data="admin_back")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.callback_query.edit_message_text(
                "✅ **All Verifications Reset!**\n\n"
                "All user verifications have been cleared.\n"
                "Users will need to complete 4-step verification again.",
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )
            
            logger.info("Admin reset all user verifications")
            
        except Exception as e:
            logger.error(f"Error resetting verifications: {e}")
            await update.callback_query.answer("❌ Error resetting verifications.")
    
    async def advertise_movie(self, update: Update, context: ContextTypes.DEFAULT_TYPE, movie_id: int):
        """Send movie advertisement to all users"""
        try:
            # Get movie details
            movie = self.db.get_movie_by_id(movie_id)
            if not movie:
                await update.callback_query.answer("❌ Movie not found.")
                return
            
            # Get all users
            user_ids = self.db.get_all_users_for_broadcast()
            
            # Create advertisement message
            ad_text = f"""
🎬 **NEW MOVIE ALERT!** 🎬

**{movie['title']}** ({movie['year']})
📺 Quality: {movie['quality']}
📁 Size: {format_file_size(movie['file_size'])}

🆕 Just uploaded! Search for it now!

⚠️ **Important:** New movies require fresh verification!
Even if you're verified, you'll need to complete verification again for new highlighted movies.

Type the movie name to search! 🔍
"""
            
            # Send to all users
            sent_count = 0
            failed_count = 0
            
            for user_id in user_ids:
                try:
                    await context.bot.send_message(
                        chat_id=user_id,
                        text=ad_text,
                        parse_mode='Markdown'
                    )
                    sent_count += 1
                except Exception:
                    failed_count += 1
            
            # Show results
            keyboard = [[InlineKeyboardButton("🔙 Back", callback_data="admin_movie_ads")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.callback_query.edit_message_text(
                f"📢 **Advertisement Sent!**\n\n"
                f"Movie: **{movie['title']}**\n"
                f"✅ Sent to: {sent_count} users\n"
                f"❌ Failed: {failed_count} users\n\n"
                f"All users have been notified about the new movie!",
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )
            
            logger.info(f"Movie advertisement sent for {movie['title']}: {sent_count} success, {failed_count} failed")
            
        except Exception as e:
            logger.error(f"Error advertising movie {movie_id}: {e}")
            await update.callback_query.answer("❌ Error sending advertisement.")
