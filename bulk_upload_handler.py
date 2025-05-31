import logging
import asyncio
from typing import List, Dict
from telegram import Update
from telegram.ext import ContextTypes
from telegram.error import TelegramError
from database import Database
from config import Config
from utils import parse_upload_caption, extract_movie_info_from_filename, format_file_size
from url_shortener import URLShortener

logger = logging.getLogger(__name__)

class BulkUploadHandler:
    """Handle bulk file uploads efficiently without hitting rate limits"""
    
    def __init__(self, database: Database):
        self.db = database
        self.url_shortener = URLShortener()
        self.upload_queue = []
        self.is_processing = False
        
    async def add_to_upload_queue(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Add file to upload queue for batch processing"""
        user = update.effective_user
        
        if user.id not in Config.ADMIN_IDS:
            return False
            
        try:
            file_obj = update.message.document or update.message.video
            if not file_obj:
                return False
                
            # Add to queue
            upload_item = {
                'file_obj': file_obj,
                'caption': update.message.caption or "",
                'user_id': user.id,
                'message': update.message,
                'context': context
            }
            
            self.upload_queue.append(upload_item)
            
            # Send quick confirmation
            await update.message.reply_text(
                f"📁 Added to upload queue (Position: {len(self.upload_queue)})\n"
                f"⏳ Processing will start automatically..."
            )
            
            # Start processing if not already running
            if not self.is_processing:
                asyncio.create_task(self._process_upload_queue())
                
            return True
            
        except Exception as e:
            logger.error(f"Error adding to upload queue: {e}")
            return False
    
    async def _process_upload_queue(self):
        """Process upload queue with proper delays to avoid rate limits"""
        if self.is_processing:
            return
            
        self.is_processing = True
        processed_count = 0
        failed_count = 0
        
        try:
            while self.upload_queue:
                # Process up to MAX_CONCURRENT_UPLOADS files simultaneously
                batch = []
                for _ in range(min(Config.MAX_CONCURRENT_UPLOADS, len(self.upload_queue))):
                    if self.upload_queue:
                        batch.append(self.upload_queue.pop(0))
                
                # Process batch concurrently
                tasks = [self._process_single_upload(item) for item in batch]
                results = await asyncio.gather(*tasks, return_exceptions=True)
                
                # Count results
                for result in results:
                    if isinstance(result, Exception):
                        failed_count += 1
                        logger.error(f"Upload failed: {result}")
                    elif result:
                        processed_count += 1
                    else:
                        failed_count += 1
                
                # Delay between batches to avoid rate limits
                if self.upload_queue:  # Only delay if more files to process
                    await asyncio.sleep(Config.BULK_UPLOAD_DELAY)
                    
        except Exception as e:
            logger.error(f"Error in bulk upload processing: {e}")
        finally:
            self.is_processing = False
            
            # Send completion summary to first admin
            if processed_count > 0 or failed_count > 0:
                try:
                    admin_id = Config.ADMIN_IDS[0]
                    summary_text = (
                        f"🎬 **Bulk Upload Complete**\n\n"
                        f"✅ Processed: {processed_count} files\n"
                        f"❌ Failed: {failed_count} files\n"
                        f"📊 Total: {processed_count + failed_count} files"
                    )
                    
                    # Send to admin through bot context (we'll need to pass this)
                    # For now, log the completion
                    logger.info(f"Bulk upload completed: {processed_count} success, {failed_count} failed")
                    
                except Exception as e:
                    logger.error(f"Error sending completion summary: {e}")
    
    async def _process_single_upload(self, upload_item: Dict) -> bool:
        """Process a single file upload"""
        try:
            file_obj = upload_item['file_obj']
            caption = upload_item['caption']
            user_id = upload_item['user_id']
            message = upload_item['message']
            context = upload_item['context']
            
            # Parse caption or auto-detect from filename
            parsed_info = parse_upload_caption(caption)
            file_name = file_obj.file_name or "unknown"
            
            if not parsed_info:
                parsed_info = extract_movie_info_from_filename(file_name)
                
                if not parsed_info['title']:
                    parsed_info = {
                        'title': file_name.replace('.', ' ').replace('_', ' '),
                        'year': None,
                        'quality': 'HD',
                        'part_season_episode': 'Complete'
                    }
            
            # Create download URL
            original_url = f"https://t.me/{context.bot.username}?start=download_{file_obj.file_id}"
            
            # Create shortened URL
            try:
                shortened_url = await self.url_shortener.shorten_url(original_url)
                if not shortened_url or shortened_url == original_url:
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
                file_size=file_obj.file_size or 0,
                original_url=original_url,
                shortened_url=shortened_url,
                uploaded_by=user_id
            )
            
            logger.info(f"Bulk uploaded: {parsed_info['title']} (ID: {movie_id})")
            return True
            
        except Exception as e:
            logger.error(f"Error processing single upload: {e}")
            return False
    
    def get_queue_status(self) -> Dict:
        """Get current queue status"""
        return {
            'queue_length': len(self.upload_queue),
            'is_processing': self.is_processing
        }