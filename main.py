import os
import logging
import asyncio
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters
from bot_handlers import BotHandlers
from database import Database
from config import Config

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    handlers=[
        logging.FileHandler('bot.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

def main():
    """Main function to start the bot"""
    try:
        # Initialize database
        db = Database()
        db.init_db()
        
        # Initialize bot handlers
        bot_handlers = BotHandlers(db)
        
        # Create application
        application = Application.builder().token(Config.BOT_TOKEN).build()
        
        # Add handlers
        application.add_handler(CommandHandler("start", bot_handlers.start_command))
        application.add_handler(CommandHandler("admin", bot_handlers.admin_command))
        application.add_handler(CommandHandler("upload", bot_handlers.upload_command))
        application.add_handler(CommandHandler("bulkupload", bot_handlers.bulk_upload_command))
        application.add_handler(CommandHandler("structure", bot_handlers.structure_command))
        application.add_handler(CommandHandler("adminchat", bot_handlers.adminchat_command))
        application.add_handler(CommandHandler("blueprint", bot_handlers.blueprint_command))
        application.add_handler(CommandHandler("verify", bot_handlers.verify_command))
        application.add_handler(CommandHandler("help", bot_handlers.help_command))
        application.add_handler(CommandHandler("stats", bot_handlers.stats_command))
        
        # Message handlers
        application.add_handler(MessageHandler(
            filters.TEXT & ~filters.COMMAND, 
            bot_handlers.handle_message
        ))
        application.add_handler(MessageHandler(
            filters.Document.ALL | filters.VIDEO, 
            bot_handlers.handle_file_upload
        ))
        
        # Callback query handler for buttons
        application.add_handler(CallbackQueryHandler(bot_handlers.handle_callback))
        
        logger.info("Starting Telegram Movie Bot...")
        
        # Start the bot  
        logger.info("Bot is starting...")
        application.run_polling(allowed_updates=['message', 'callback_query'])
        
    except Exception as e:
        logger.error(f"Failed to start bot: {e}")
        raise

if __name__ == "__main__":
    main()
