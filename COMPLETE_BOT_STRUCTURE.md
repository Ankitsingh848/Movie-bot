# Complete Telegram Movie Filter Bot Structure

## Overview
यह एक complete Telegram movie filter bot है जो auto movie search, download, और file management करता है।

## Required Environment Variables
```bash
BOT_TOKEN=your_telegram_bot_token_from_botfather
ADMIN_IDS=your_admin_user_id (comma separated for multiple admins)
INSHORT_API_KEY=your_inshort_api_key_for_url_shortening
```

## Dependencies (pyproject.toml)
```toml
[project]
name = "telegram-movie-bot"
version = "1.0.0"
dependencies = [
    "python-telegram-bot[job-queue]==20.8",
    "aiohttp==3.12.2",
    "fuzzywuzzy==0.18.0",
    "python-levenshtein==0.27.1"
]

[build-system]
requires = ["setuptools", "wheel"]
build-backend = "setuptools.build_meta"
```

## File Structure
```
movie-bot/
├── main.py                 # Main bot runner
├── config.py              # Configuration settings
├── database.py            # Database operations
├── bot_handlers.py        # Main bot logic
├── url_shortener.py       # URL shortening service
├── utils.py               # Helper functions
├── admin_panel.py         # Admin panel features
├── bulk_upload_handler.py # Bulk upload system
├── admin_chat_system.py   # Admin chat system
├── bot_structure_viewer.py # Code viewer
├── bot_blueprint_generator.py # Blueprint generator
└── movie_bot.db           # SQLite database (auto-created)
```

## Core Features
1. **Auto Movie Search** - Fuzzy search with spell correction
2. **Direct Download** - One-click file download
3. **Admin Panel** - Complete admin management
4. **Bulk Upload** - Handle multiple files
5. **Auto Delete** - Files auto-delete after 10 minutes
6. **Rate Limiting** - Prevents spam
7. **User Analytics** - Complete user tracking
8. **Admin Chat** - Direct chat with users

## Commands
### User Commands
- `/start` - Start the bot
- `/help` - Show help message
- Search by typing movie name

### Admin Commands
- `/admin` - Admin panel
- `/upload` - Upload single file
- `/bulkupload` - Bulk upload
- `/stats` - Bot statistics
- `/structure` - View bot code
- `/adminchat` - Chat with users
- `/blueprint` - Generate bot blueprint

## Database Schema
```sql
-- Movies table
CREATE TABLE movies (
    id INTEGER PRIMARY KEY,
    title TEXT NOT NULL,
    year INTEGER,
    quality TEXT,
    part_season_episode TEXT,
    file_id TEXT UNIQUE NOT NULL,
    file_name TEXT NOT NULL,
    file_size INTEGER DEFAULT 0,
    original_url TEXT NOT NULL,
    shortened_url TEXT NOT NULL,
    uploaded_by INTEGER NOT NULL,
    upload_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    download_count INTEGER DEFAULT 0,
    is_active BOOLEAN DEFAULT 1
);

-- User information
CREATE TABLE users (
    user_id INTEGER PRIMARY KEY,
    username TEXT,
    first_name TEXT,
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Search logs
CREATE TABLE search_logs (
    id INTEGER PRIMARY KEY,
    user_id INTEGER,
    username TEXT,
    query TEXT,
    results_count INTEGER,
    search_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Download logs
CREATE TABLE download_logs (
    id INTEGER PRIMARY KEY,
    user_id INTEGER,
    username TEXT,
    movie_id INTEGER,
    download_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    auto_delete_time TIMESTAMP,
    is_deleted BOOLEAN DEFAULT 0
);

-- Rate limiting
CREATE TABLE rate_limits (
    user_id INTEGER,
    action TEXT,
    count INTEGER DEFAULT 1,
    reset_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (user_id, action)
);

-- User messages (for admin monitoring)
CREATE TABLE user_messages (
    id INTEGER PRIMARY KEY,
    user_id INTEGER,
    username TEXT,
    message_text TEXT,
    message_type TEXT DEFAULT 'text',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Movie requests
CREATE TABLE movie_requests (
    id INTEGER PRIMARY KEY,
    user_id INTEGER,
    username TEXT,
    movie_name TEXT,
    status TEXT DEFAULT 'pending',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- URL visits (for verification)
CREATE TABLE url_visits (
    id INTEGER PRIMARY KEY,
    user_id INTEGER,
    movie_id INTEGER,
    shortened_url TEXT,
    verification_token TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    visit_time TIMESTAMP
);
```

## Setup Instructions

### 1. Create Telegram Bot
1. Message @BotFather on Telegram
2. Create new bot with `/newbot`
3. Get BOT_TOKEN
4. Get your user ID (message @userinfobot)

### 2. Get InShort API Key
1. Visit inshorturl.com
2. Register for API access
3. Get API key

### 3. Installation
```bash
# Clone or create project directory
mkdir telegram-movie-bot
cd telegram-movie-bot

# Set environment variables
export BOT_TOKEN="your_bot_token"
export ADMIN_IDS="your_user_id"
export INSHORT_API_KEY="your_api_key"

# Install dependencies
pip install python-telegram-bot[job-queue]==20.8 aiohttp==3.12.2 fuzzywuzzy==0.18.0 python-levenshtein==0.27.1

# Run the bot
python main.py
```

## Configuration Options
All settings can be modified in `config.py`:

- **File Types**: Supported video/audio formats
- **File Size**: No limit (uses Telegram cloud)
- **Auto Delete**: Default 10 minutes
- **Rate Limits**: Search/upload limits
- **Backup Channel**: Force join settings
- **Fuzzy Search**: Similarity threshold

## Usage Flow
1. **User searches** for movie name
2. **Bot shows results** with download buttons
3. **User clicks button** → File sent instantly to DM
4. **File auto-deletes** after 10 minutes
5. **Admin can upload** new movies via `/upload`
6. **Admin can manage** everything via `/admin`

## Deployment
Bot can be deployed on:
- **Local Server** - Run directly
- **VPS** - Cloud server deployment
- **Replit** - Online IDE platform
- **Heroku** - Cloud platform
- **Railway** - Modern cloud platform

## Security Features
- **Admin-only uploads** - Only authorized users can upload
- **Rate limiting** - Prevents spam and abuse
- **Auto cleanup** - Files delete automatically
- **User tracking** - Complete audit trail
- **Error handling** - Robust error management

## Advanced Features
- **Fuzzy search** - Works with typos
- **Bulk operations** - Handle multiple files
- **Admin chat** - Direct user communication
- **Analytics** - Detailed usage statistics
- **Code viewer** - See bot structure
- **Blueprint generator** - Create copies

## Troubleshooting
1. **Bot not responding** - Check BOT_TOKEN
2. **Upload fails** - Verify admin ID
3. **URL shortening fails** - Check INSHORT_API_KEY
4. **Database errors** - Check file permissions
5. **Rate limit issues** - Adjust config settings

## Customization
Bot can be customized for:
- **Different file types** - Documents, images, etc.
- **Custom commands** - Add new features
- **Different databases** - PostgreSQL, MySQL
- **Custom UI** - Modify messages and buttons
- **Integration** - Connect with other services

## License
Open source - modify and use freely

## Support
For issues or questions:
1. Check logs in `bot.log`
2. Verify environment variables
3. Test with simple commands first
4. Check admin permissions

---
**Note**: This bot is for educational purposes. Ensure compliance with copyright laws and Telegram's Terms of Service.