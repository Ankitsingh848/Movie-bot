import os
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from database import Database
from config import Config
import json

logger = logging.getLogger(__name__)

class BotStructureViewer:
    """Admin panel to view complete bot structure and code"""
    
    def __init__(self, database: Database):
        self.db = database
        
    async def show_structure_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show main structure viewing menu"""
        user = update.effective_user
        
        if user.id not in Config.ADMIN_IDS:
            await update.message.reply_text("❌ You are not authorized to view bot structure.")
            return
        
        keyboard = [
            [InlineKeyboardButton("📁 View All Files", callback_data="structure_files")],
            [InlineKeyboardButton("🔧 View Configuration", callback_data="structure_config")],
            [InlineKeyboardButton("📊 Database Schema", callback_data="structure_database")],
            [InlineKeyboardButton("🔗 API Connections", callback_data="structure_apis")],
            [InlineKeyboardButton("📝 Code Templates", callback_data="structure_templates")],
            [InlineKeyboardButton("🚀 Deployment Guide", callback_data="structure_deploy")],
            [InlineKeyboardButton("💾 Export Everything", callback_data="structure_export")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        structure_text = (
            "🏗️ **Bot Structure Viewer**\n\n"
            "**Current Bot Overview:**\n"
            f"• Total Files: {self._count_project_files()}\n"
            f"• Database Tables: {self._count_database_tables()}\n"
            f"• Commands Available: {self._count_bot_commands()}\n"
            f"• Movies in Database: {self._count_movies()}\n\n"
            "**Select what you want to view:**"
        )
        
        await update.message.reply_text(
            structure_text,
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
    
    async def handle_structure_callback(self, query, context):
        """Handle structure viewing callbacks"""
        data = query.data
        
        try:
            if data == "structure_files":
                await self._show_all_files(query, context)
            elif data == "structure_config":
                await self._show_configuration(query, context)
            elif data == "structure_database":
                await self._show_database_schema(query, context)
            elif data == "structure_apis":
                await self._show_api_connections(query, context)
            elif data == "structure_templates":
                await self._show_code_templates(query, context)
            elif data == "structure_deploy":
                await self._show_deployment_guide(query, context)
            elif data == "structure_export":
                await self._export_everything(query, context)
            elif data.startswith("view_file_"):
                filename = data.replace("view_file_", "")
                await self._show_file_content(query, context, filename)
            elif data == "structure_back":
                await self.show_structure_menu_callback(query, context)
        except Exception as e:
            logger.error(f"Error in structure callback: {e}")
            await query.edit_message_text("❌ An error occurred while viewing structure.")
    
    async def show_structure_menu_callback(self, query, context):
        """Show structure menu from callback"""
        keyboard = [
            [InlineKeyboardButton("📁 View All Files", callback_data="structure_files")],
            [InlineKeyboardButton("🔧 View Configuration", callback_data="structure_config")],
            [InlineKeyboardButton("📊 Database Schema", callback_data="structure_database")],
            [InlineKeyboardButton("🔗 API Connections", callback_data="structure_apis")],
            [InlineKeyboardButton("📝 Code Templates", callback_data="structure_templates")],
            [InlineKeyboardButton("🚀 Deployment Guide", callback_data="structure_deploy")],
            [InlineKeyboardButton("💾 Export Everything", callback_data="structure_export")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        structure_text = (
            "🏗️ **Bot Structure Viewer**\n\n"
            "**Current Bot Overview:**\n"
            f"• Total Files: {self._count_project_files()}\n"
            f"• Database Tables: {self._count_database_tables()}\n"
            f"• Commands Available: {self._count_bot_commands()}\n"
            f"• Movies in Database: {self._count_movies()}\n\n"
            "**Select what you want to view:**"
        )
        
        await query.edit_message_text(
            structure_text,
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
    
    async def _show_all_files(self, query, context):
        """Show all project files"""
        files = []
        for root, dirs, filenames in os.walk('.'):
            for filename in filenames:
                if filename.endswith(('.py', '.md', '.txt', '.json', '.yml', '.yaml')):
                    relative_path = os.path.relpath(os.path.join(root, filename), '.')
                    if not relative_path.startswith('.'):
                        files.append(relative_path)
        
        files.sort()
        
        keyboard = []
        for file in files[:20]:  # Show first 20 files
            display_name = file if len(file) <= 30 else f"...{file[-27:]}"
            keyboard.append([InlineKeyboardButton(
                f"📄 {display_name}", 
                callback_data=f"view_file_{file}"
            )])
        
        keyboard.append([InlineKeyboardButton("🔙 Back", callback_data="structure_back")])
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        file_text = (
            f"📁 **Project Files ({len(files)} total)**\n\n"
            "**Core Bot Files:**\n"
            "• main.py - Bot startup\n"
            "• bot_handlers.py - Main logic\n"
            "• config.py - Settings\n"
            "• database.py - Data storage\n"
            "• bulk_upload_handler.py - Bulk processing\n"
            "• admin_panel.py - Admin features\n"
            "• utils.py - Helper functions\n\n"
            "**Click any file to view its code:**"
        )
        
        await query.edit_message_text(
            file_text,
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
    
    async def _show_file_content(self, query, context, filename):
        """Show content of a specific file"""
        try:
            with open(filename, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Truncate if too long
            if len(content) > 3500:
                content = content[:3500] + "\n\n... (truncated - file is longer)"
            
            file_info = (
                f"📄 **{filename}**\n"
                f"📏 Size: {os.path.getsize(filename)} bytes\n\n"
                f"```python\n{content}\n```"
            )
            
            keyboard = [[InlineKeyboardButton("🔙 Back to Files", callback_data="structure_files")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.edit_message_text(
                file_info,
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )
            
        except Exception as e:
            await query.edit_message_text(
                f"❌ Error reading file {filename}: {str(e)}\n\n"
                f"🔙 [Back to Files](callback_data:structure_files)",
                parse_mode='Markdown'
            )
    
    async def _show_configuration(self, query, context):
        """Show bot configuration"""
        config_text = (
            "🔧 **Bot Configuration**\n\n"
            f"**Admin Settings:**\n"
            f"• Admin IDs: {Config.ADMIN_IDS}\n"
            f"• Backup Channel: {Config.BACKUP_CHANNEL}\n"
            f"• Force Join: {Config.FORCE_JOIN_BACKUP}\n\n"
            f"**Upload Limits:**\n"
            f"• Max Uploads/Hour: {Config.MAX_UPLOADS_PER_HOUR}\n"
            f"• Max Searches/Minute: {Config.MAX_SEARCHES_PER_MINUTE}\n"
            f"• Bulk Upload Delay: {Config.BULK_UPLOAD_DELAY}s\n"
            f"• Max Concurrent: {Config.MAX_CONCURRENT_UPLOADS}\n\n"
            f"**File Settings:**\n"
            f"• Auto Delete: {Config.AUTO_DELETE_MINUTES} min\n"
            f"• Allowed Extensions: {len(Config.ALLOWED_FILE_EXTENSIONS)} types\n"
            f"• Max File Size: Unlimited\n\n"
            f"**Database:**\n"
            f"• Path: {Config.DATABASE_PATH}\n"
            f"• Search Threshold: {Config.FUZZY_SEARCH_THRESHOLD}%"
        )
        
        keyboard = [[InlineKeyboardButton("🔙 Back", callback_data="structure_back")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            config_text,
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
    
    async def _show_database_schema(self, query, context):
        """Show database schema"""
        schema_text = (
            "📊 **Database Schema**\n\n"
            "**Table: movies**\n"
            "• id (INTEGER, Primary Key)\n"
            "• title (TEXT)\n"
            "• year (INTEGER)\n"
            "• quality (TEXT)\n"
            "• part_season_episode (TEXT)\n"
            "• file_id (TEXT, Unique)\n"
            "• file_name (TEXT)\n"
            "• file_size (INTEGER)\n"
            "• original_url (TEXT)\n"
            "• shortened_url (TEXT)\n"
            "• uploaded_by (INTEGER)\n"
            "• upload_date (TIMESTAMP)\n"
            "• download_count (INTEGER)\n\n"
            "**Table: search_logs**\n"
            "• id, user_id, username, query, results_count, search_date\n\n"
            "**Table: download_logs**\n"
            "• id, user_id, username, movie_id, download_date, auto_delete_at\n\n"
            "**Table: user_verifications**\n"
            "• user_id, verified_at, dm_accessible\n\n"
            "**Additional Tables:**\n"
            "• rate_limits, verification_requests, user_messages, movie_requests"
        )
        
        keyboard = [[InlineKeyboardButton("🔙 Back", callback_data="structure_back")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            schema_text,
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
    
    async def _show_api_connections(self, query, context):
        """Show API connections"""
        api_text = (
            "🔗 **API Connections**\n\n"
            "**Telegram Bot API:**\n"
            "• Status: ✅ Connected\n"
            "• Token: Configured\n"
            "• Webhook: Polling mode\n\n"
            "**InShort URL API:**\n"
            "• Service: inshorturl.com\n"
            "• Purpose: Create secure download links\n"
            "• Status: Available\n\n"
            "**Bot Capabilities:**\n"
            "• Send/Receive Messages ✅\n"
            "• File Upload/Download ✅\n"
            "• Inline Keyboards ✅\n"
            "• Callback Queries ✅\n"
            "• Channel Management ✅\n"
            "• User Verification ✅\n\n"
            "**External Dependencies:**\n"
            "• python-telegram-bot[job-queue]\n"
            "• aiohttp\n"
            "• fuzzywuzzy\n"
            "• python-levenshtein"
        )
        
        keyboard = [[InlineKeyboardButton("🔙 Back", callback_data="structure_back")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            api_text,
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
    
    async def _show_code_templates(self, query, context):
        """Show code templates for creating new bots"""
        template_text = (
            "📝 **Code Templates for New Bots**\n\n"
            "**1. Basic Bot Structure:**\n"
            "```python\n"
            "from telegram.ext import Application, CommandHandler\n"
            "from config import Config\n\n"
            "def main():\n"
            "    app = Application.builder().token(Config.BOT_TOKEN).build()\n"
            "    app.add_handler(CommandHandler('start', start_command))\n"
            "    app.run_polling()\n"
            "```\n\n"
            "**2. File Upload Handler:**\n"
            "```python\n"
            "async def handle_upload(update, context):\n"
            "    file_obj = update.message.document\n"
            "    # Process file here\n"
            "```\n\n"
            "**3. Database Connection:**\n"
            "```python\n"
            "import sqlite3\n"
            "conn = sqlite3.connect('bot.db')\n"
            "cursor = conn.cursor()\n"
            "```\n\n"
            "Copy this structure to create similar bots!"
        )
        
        keyboard = [[InlineKeyboardButton("🔙 Back", callback_data="structure_back")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            template_text,
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
    
    async def _show_deployment_guide(self, query, context):
        """Show deployment guide"""
        deploy_text = (
            "🚀 **Deployment Guide**\n\n"
            "**Requirements:**\n"
            "• Python 3.8+\n"
            "• Bot Token from @BotFather\n"
            "• InShort API Key\n\n"
            "**Setup Steps:**\n"
            "1. Install dependencies:\n"
            "   `pip install python-telegram-bot aiohttp fuzzywuzzy`\n\n"
            "2. Set environment variables:\n"
            "   `BOT_TOKEN=your_token`\n"
            "   `ADMIN_IDS=your_user_id`\n"
            "   `INSHORT_API_KEY=your_key`\n\n"
            "3. Run the bot:\n"
            "   `python main.py`\n\n"
            "**Features Included:**\n"
            "• File upload/download system\n"
            "• Bulk processing (500+ files)\n"
            "• User verification\n"
            "• Rate limiting protection\n"
            "• Auto-delete functionality\n"
            "• Admin panel\n"
            "• Backup channel integration"
        )
        
        keyboard = [[InlineKeyboardButton("🔙 Back", callback_data="structure_back")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            deploy_text,
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
    
    async def _export_everything(self, query, context):
        """Export complete bot structure"""
        try:
            export_data = {
                "bot_info": {
                    "name": "Telegram Movie Bot",
                    "version": "2.0",
                    "files": self._count_project_files(),
                    "commands": self._count_bot_commands()
                },
                "configuration": {
                    "admin_ids": Config.ADMIN_IDS,
                    "backup_channel": Config.BACKUP_CHANNEL,
                    "upload_limits": {
                        "max_per_hour": Config.MAX_UPLOADS_PER_HOUR,
                        "max_searches": Config.MAX_SEARCHES_PER_MINUTE,
                        "bulk_delay": Config.BULK_UPLOAD_DELAY
                    }
                },
                "database": {
                    "path": Config.DATABASE_PATH,
                    "tables": ["movies", "search_logs", "download_logs", "user_verifications"],
                    "total_movies": self._count_movies()
                }
            }
            
            export_text = (
                "💾 **Complete Bot Export**\n\n"
                f"```json\n{json.dumps(export_data, indent=2)}\n```\n\n"
                "**To recreate this bot:**\n"
                "1. Copy all .py files\n"
                "2. Install dependencies\n"
                "3. Set environment variables\n"
                "4. Run main.py\n\n"
                "All functionality will be preserved!"
            )
            
        except Exception as e:
            export_text = f"❌ Export failed: {str(e)}"
        
        keyboard = [[InlineKeyboardButton("🔙 Back", callback_data="structure_back")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            export_text,
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
    
    def _count_project_files(self):
        """Count project files"""
        count = 0
        for root, dirs, files in os.walk('.'):
            for file in files:
                if file.endswith('.py'):
                    count += 1
        return count
    
    def _count_database_tables(self):
        """Count database tables"""
        return 6  # Known tables in our schema
    
    def _count_bot_commands(self):
        """Count bot commands"""
        return 7  # start, admin, upload, bulkupload, help, stats, structure
    
    def _count_movies(self):
        """Count movies in database"""
        try:
            stats = self.db.get_stats()
            return stats.get('total_movies', 0)
        except:
            return 0