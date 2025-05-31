import os
import logging
import asyncio
from typing import Optional, Dict, List
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

class FileManager:
    """File management utilities for the bot"""
    
    def __init__(self):
        self.temp_dir = "temp_files"
        self.ensure_temp_directory()
    
    def ensure_temp_directory(self):
        """Ensure temporary directory exists"""
        if not os.path.exists(self.temp_dir):
            os.makedirs(self.temp_dir)
            logger.info(f"Created temporary directory: {self.temp_dir}")
    
    async def download_file(self, file_url: str, filename: str) -> Optional[str]:
        """Download a file from URL and save to temp directory"""
        try:
            import aiohttp
            
            file_path = os.path.join(self.temp_dir, filename)
            
            async with aiohttp.ClientSession() as session:
                async with session.get(file_url) as response:
                    if response.status == 200:
                        with open(file_path, 'wb') as f:
                            async for chunk in response.content.iter_chunked(8192):
                                f.write(chunk)
                        
                        logger.info(f"Downloaded file: {filename}")
                        return file_path
                    else:
                        logger.error(f"Failed to download file: HTTP {response.status}")
                        
        except Exception as e:
            logger.error(f"Error downloading file {filename}: {e}")
        
        return None
    
    def get_file_info(self, file_path: str) -> Optional[Dict]:
        """Get file information"""
        try:
            if not os.path.exists(file_path):
                return None
            
            stat = os.stat(file_path)
            
            return {
                'size': stat.st_size,
                'created': datetime.fromtimestamp(stat.st_ctime),
                'modified': datetime.fromtimestamp(stat.st_mtime),
                'name': os.path.basename(file_path),
                'extension': os.path.splitext(file_path)[1]
            }
            
        except Exception as e:
            logger.error(f"Error getting file info for {file_path}: {e}")
            return None
    
    def delete_file(self, file_path: str) -> bool:
        """Delete a file"""
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
                logger.info(f"Deleted file: {file_path}")
                return True
            else:
                logger.warning(f"File not found for deletion: {file_path}")
                return False
                
        except Exception as e:
            logger.error(f"Error deleting file {file_path}: {e}")
            return False
    
    def cleanup_old_files(self, max_age_hours: int = 24) -> int:
        """Clean up old temporary files"""
        deleted_count = 0
        cutoff_time = datetime.now() - timedelta(hours=max_age_hours)
        
        try:
            for filename in os.listdir(self.temp_dir):
                file_path = os.path.join(self.temp_dir, filename)
                
                if os.path.isfile(file_path):
                    file_info = self.get_file_info(file_path)
                    
                    if file_info and file_info['created'] < cutoff_time:
                        if self.delete_file(file_path):
                            deleted_count += 1
            
            logger.info(f"Cleaned up {deleted_count} old files")
            
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")
        
        return deleted_count
    
    def get_temp_file_path(self, filename: str) -> str:
        """Get full path for a temporary file"""
        return os.path.join(self.temp_dir, filename)
    
    def is_valid_video_file(self, filename: str) -> bool:
        """Check if file is a valid video file"""
        from config import Config
        
        return any(filename.lower().endswith(ext) for ext in Config.ALLOWED_FILE_EXTENSIONS)
    
    def generate_unique_filename(self, base_name: str, extension: str) -> str:
        """Generate a unique filename"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        return f"{base_name}_{timestamp}{extension}"
    
    async def validate_file_integrity(self, file_path: str) -> bool:
        """Validate file integrity (basic check)"""
        try:
            file_info = self.get_file_info(file_path)
            
            if not file_info:
                return False
            
            # Check if file size is reasonable
            if file_info['size'] == 0:
                logger.warning(f"File is empty: {file_path}")
                return False
            
            # Check if file is too large
            from config import Config
            if file_info['size'] > Config.MAX_FILE_SIZE * 2:  # Allow some buffer
                logger.warning(f"File too large: {file_path}")
                return False
            
            # Try to read first few bytes to ensure file is accessible
            with open(file_path, 'rb') as f:
                header = f.read(1024)
                if not header:
                    logger.warning(f"Cannot read file header: {file_path}")
                    return False
            
            return True
            
        except Exception as e:
            logger.error(f"Error validating file integrity {file_path}: {e}")
            return False
    
    def get_directory_size(self, directory: str = None) -> int:
        """Get total size of directory"""
        if directory is None:
            directory = self.temp_dir
            
        total_size = 0
        
        try:
            for dirpath, dirnames, filenames in os.walk(directory):
                for filename in filenames:
                    file_path = os.path.join(dirpath, filename)
                    if os.path.exists(file_path):
                        total_size += os.path.getsize(file_path)
            
        except Exception as e:
            logger.error(f"Error calculating directory size: {e}")
        
        return total_size
    
    def list_temp_files(self) -> List[Dict]:
        """List all files in temp directory with info"""
        files = []
        
        try:
            for filename in os.listdir(self.temp_dir):
                file_path = os.path.join(self.temp_dir, filename)
                
                if os.path.isfile(file_path):
                    file_info = self.get_file_info(file_path)
                    if file_info:
                        file_info['path'] = file_path
                        files.append(file_info)
            
        except Exception as e:
            logger.error(f"Error listing temp files: {e}")
        
        return files
    
    async def schedule_file_deletion(self, file_path: str, delay_seconds: int):
        """Schedule a file for deletion after specified delay"""
        try:
            await asyncio.sleep(delay_seconds)
            self.delete_file(file_path)
            logger.info(f"Scheduled deletion completed for: {file_path}")
            
        except Exception as e:
            logger.error(f"Error in scheduled deletion for {file_path}: {e}")
