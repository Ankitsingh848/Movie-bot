import os
from typing import List

class Config:
    """Configuration class for the Telegram Movie Bot"""
    
    # Bot configuration
    BOT_TOKEN = os.getenv("BOT_TOKEN", "")
    BOT_USERNAME = os.getenv("BOT_USERNAME", "YourBotUsername")
    
    # Admin configuration
    ADMIN_IDS = [
        int(admin_id.strip()) 
        for admin_id in os.getenv("ADMIN_IDS", "8148695660").split(",") 
        if admin_id.strip().isdigit()
    ]
    
    # URL shortener configuration
    INSHORT_API_KEY = os.getenv("INSHORT_API_KEY", "2768027b01bf104bca0240ed41ebd4e191df15cc")
    INSHORT_API_TOKEN = os.getenv("INSHORT_API_TOKEN", "2768027b01bf104bca0240ed41ebd4e191df15cc")
    INSHORT_API_URL = "https://inshorturl.com/api"
    
    # File configuration
    MAX_FILE_SIZE = None  # No file size limit - accept any size
    ALLOWED_FILE_EXTENSIONS = ['.mp4', '.mkv', '.avi', '.mov', '.wmv', '.flv', '.webm', '.m4v', '.mp3', '.wav', '.pdf', '.txt', '.zip', '.rar']
    
    # Auto-delete configuration
    AUTO_DELETE_MINUTES = 10
    
    # Database configuration
    DATABASE_PATH = "movie_bot.db"
    
    # Search configuration
    FUZZY_SEARCH_THRESHOLD = 60  # Minimum similarity percentage
    MAX_SEARCH_RESULTS = 10
    
    # Rate limiting - Optimized for bulk uploads
    MAX_SEARCHES_PER_MINUTE = 10
    MAX_UPLOADS_PER_HOUR = 1000  # Allow bulk uploads
    BULK_UPLOAD_DELAY = 0.5  # Delay between bulk uploads in seconds
    MAX_CONCURRENT_UPLOADS = 5  # Process multiple files simultaneously
    
    # Backup channel configuration
    BACKUP_CHANNEL = "https://t.me/+gU0yZrOEFbliNThl"
    BACKUP_CHANNEL_ID = "@moviebackupchannel"  # Replace with actual channel username
    FORCE_JOIN_BACKUP = False  # Require users to join backup channel
    
    # Messages
    WELCOME_MESSAGE = """
🎬 **Welcome to Movie Filter Bot!**

**For Users:**
• Search for movies/series by typing the name
• I'll find matches even with spelling mistakes
• Click on buttons to get direct download links
• Files will be sent to your DM instantly

**Commands:**
/help - Show this help message

**Note:** This bot is for educational purposes only.
"""
    
    ADMIN_WELCOME_MESSAGE = """
🔐 **Admin Panel**

**Commands:**
/upload - Upload a new movie/series
/stats - View bot statistics
/admin - Show admin commands

**Upload Format:**
Send a file with caption in format:
`Movie Name | Year | Quality | Part/Season/Episode`

Example: `Avengers Endgame | 2019 | 1080p | Part 1`
"""
    
    HELP_MESSAGE = """
🆘 **Help & Instructions**

**How to search:**
1. Type the movie/series name
2. I'll show matching results with buttons
3. Click on the button to get the file
4. File will be sent to your DM

**Search Tips:**
• You can make spelling mistakes, I'll still find it!
• Use keywords like "avengers", "season 1", "part 2"
• Be specific for better results

**Note:** Files are automatically deleted after 10 minutes for copyright protection.
"""

    @classmethod
    def validate_config(cls) -> bool:
        """Validate that all required configuration is present"""
        if not cls.BOT_TOKEN:
            raise ValueError("BOT_TOKEN environment variable is required")
        
        if not cls.ADMIN_IDS:
            raise ValueError("ADMIN_IDS environment variable is required")
            
        if not cls.INSHORT_API_KEY:
            raise ValueError("INSHORT_API_KEY environment variable is required for verification system")
            
        return True
