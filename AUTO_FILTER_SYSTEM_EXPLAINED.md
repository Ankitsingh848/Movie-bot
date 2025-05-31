# Complete Auto Filter Movie Bot with Daily Verification System

## System Overview

यह एक advanced auto filter movie bot है जो daily verification system के साथ काम करता है। हर user को एक दिन में एक बार verification करना होता है, जिसके बाद 24 hours तक सभी movies free access मिलती है।

## Core System Components

### 1. Database Tables Structure

#### Users Table (users)
```sql
- user_id (BigInteger, Primary Key) - Telegram user ID
- username (String) - Telegram username
- first_name (String) - User का first name
- last_name (String) - User का last name
- is_banned (Boolean) - User banned है या नहीं
- is_premium (Boolean) - Premium user status
- join_date (DateTime) - जब user ने bot start किया
- last_active (DateTime) - Last activity time
- last_verified (DateTime) - Last verification time
- verification_count (Integer) - Total verifications count
```

#### Movies Table (movies)
```sql
- id (Integer, Primary Key) - Movie ID
- title (String) - Movie name
- year (Integer) - Release year
- quality (String) - Video quality (1080p, 720p, etc.)
- language (String) - Movie language (Hindi, English, etc.)
- genre (String) - Movie genre
- file_id (String, Unique) - Telegram file ID
- file_name (String) - Original file name
- file_size (BigInteger) - File size in bytes
- file_type (String) - video/document
- uploaded_by (BigInteger) - Admin ID who uploaded
- upload_date (DateTime) - Upload timestamp
- download_count (Integer) - Total downloads
- search_count (Integer) - Total searches
- is_active (Boolean) - Movie active status
- is_featured (Boolean) - Featured movie status
```

#### User Verifications Table (user_verifications)
```sql
- id (Integer, Primary Key) - Verification ID
- user_id (BigInteger) - User ID
- movie_id (Integer) - Movie ID for which verification was created
- verification_token (String, Unique) - Unique verification token
- short_url (String) - Shortened URL for verification
- original_url (String) - Original bot URL
- created_at (DateTime) - Verification creation time
- expires_at (DateTime) - Verification expiry time
- verified_at (DateTime) - When user completed verification
- is_verified (Boolean) - Verification completed status
- is_expired (Boolean) - Verification expired status
```

#### Download Logs Table (download_logs)
```sql
- id (Integer, Primary Key) - Download ID
- user_id (BigInteger) - User ID
- movie_id (Integer) - Movie ID
- download_method (String) - telegram/direct
- file_sent (Boolean) - File successfully sent
- requested_at (DateTime) - Download request time
- completed_at (DateTime) - Download completion time
- auto_delete_time (DateTime) - Scheduled auto-delete time
- is_deleted (Boolean) - File deleted status
```

#### Search Logs Table (search_logs)
```sql
- id (Integer, Primary Key) - Search ID
- user_id (BigInteger) - User ID
- query (String) - Search query
- results_count (Integer) - Number of results found
- search_date (DateTime) - Search timestamp
```

#### URL Shorteners Table (url_shorteners)
```sql
- id (Integer, Primary Key) - URL ID
- original_url (String) - Original bot URL
- short_url (String) - Shortened URL
- short_code (String, Unique) - Short code
- click_count (Integer) - URL click count
- created_at (DateTime) - Creation time
- expires_at (DateTime) - Expiry time
- verification_id (Integer) - Associated verification ID
```

## System Flow Explanation

### 1. User Journey

#### New User (First Time):
1. User sends `/start` command
2. Bot saves user info in database
3. User types movie name
4. Bot shows search results with download buttons
5. User clicks download button
6. Bot checks verification status → Needs verification
7. Bot creates verification request with unique token
8. Bot generates shortened URL using InShort API
9. Bot sends verification message with short URL
10. User clicks short URL → Gets redirected to bot with verification token
11. Bot verifies token and marks user as verified for 24 hours
12. Bot sends requested movie file
13. File auto-deletes after configured time

#### Returning User (Within 24 Hours):
1. User searches for movie
2. User clicks download button
3. Bot checks verification status → Already verified
4. Bot sends file directly without verification

#### Returning User (After 24 Hours):
1. Same process as new user - needs fresh verification

### 2. Verification System Details

#### Token Generation:
```python
def _generate_verification_token(user_id, movie_id):
    timestamp = current_timestamp
    unique_string = f"{user_id}_{movie_id}_{timestamp}_{random_uuid}"
    token = md5_hash(unique_string)
    return token
```

#### Short URL Creation:
```python
def create_short_url(original_url, token):
    # Call InShort API
    data = {
        'url': original_url,
        'api': INSHORT_API_KEY
    }
    response = api_call(data)
    return response.shortened_url
```

#### Verification Process:
```python
def verify_user(verification_token):
    verification = get_verification_by_token(token)
    if verification.is_valid():
        user = get_user(verification.user_id)
        user.mark_verified()  # Valid for 24 hours
        return success_response
    else:
        return failure_response
```

### 3. File Management System

#### Upload Process:
1. Admin sends file with caption format: `Movie Name | Year | Quality | Language`
2. Bot parses caption and extracts movie details
3. Bot saves file_id and movie info to database
4. Movie becomes searchable immediately

#### Download Process:
1. Bot gets movie details from database
2. Bot checks user verification status
3. If verified: Send file directly using Telegram file_id
4. If not verified: Show verification requirement
5. Schedule auto-delete job for file

#### Auto-Delete System:
```python
def auto_delete_file(user_id, movie_title):
    # Runs after configured minutes
    send_message(user_id, f"File {movie_title} auto-deleted")
    # File is deleted from user's chat automatically
```

### 4. Search System

#### Fuzzy Search:
```python
def search_movies(query):
    # Search in title, quality, language fields
    movies = database.query(
        Movie.title.contains(query) OR
        Movie.quality.contains(query) OR
        Movie.language.contains(query)
    ).order_by(Movie.download_count.desc())
    return movies
```

#### Search Logging:
- Every search query is logged
- Results count is tracked
- User search patterns are analyzed

### 5. Admin Features

#### Movie Upload:
- Format: `Title | Year | Quality | Language`
- Automatic file info extraction
- Instant availability for search

#### Statistics Dashboard:
- Total users, movies, downloads
- Verification success rates
- Search analytics
- User activity patterns

## Environment Variables Required

```bash
# Bot Configuration
BOT_TOKEN=your_telegram_bot_token
BOT_USERNAME=your_bot_username
ADMIN_IDS=comma_separated_admin_user_ids

# Database
DATABASE_URL=postgresql_connection_string

# URL Shortener
INSHORT_API_KEY=your_inshort_api_key

# App Settings
AUTO_DELETE_MINUTES=10
FLASK_SECRET_KEY=your_secret_key
```

## File Structure

```
auto-filter-bot/
├── models.py                  # Database models
├── verification_system.py     # Verification logic
├── auto_filter_bot.py        # Main bot file
├── config.py                 # Configuration
├── utils.py                  # Helper functions
└── requirements.txt          # Dependencies
```

## Key Features

### 1. Daily Verification System
- Each user needs to verify once per day
- 24-hour validity period
- Unique tokens for security
- Shortened URLs for better UX

### 2. Smart File Management
- Telegram cloud storage
- Auto-delete for copyright protection
- Download tracking
- File size optimization

### 3. Advanced Search
- Typo-tolerant search
- Multiple field search
- Result ranking by popularity
- Search analytics

### 4. Admin Panel
- Easy file upload
- User management
- Statistics dashboard
- Verification monitoring

### 5. User Experience
- Hindi language interface
- Simple button-based navigation
- Clear instructions
- Status tracking

## Security Features

1. **Unique Tokens**: Every verification request has unique token
2. **Time Expiry**: Verification links expire after 24 hours
3. **Rate Limiting**: Prevents spam and abuse
4. **Admin Only Uploads**: Only authorized users can upload
5. **Auto Cleanup**: Old verifications are cleaned up

## Scalability Features

1. **PostgreSQL Database**: Handles large datasets
2. **Efficient Queries**: Optimized for performance
3. **Background Jobs**: Auto-delete and cleanup
4. **API Integration**: External URL shortener
5. **Modular Design**: Easy to extend

## Monitoring & Analytics

1. **User Analytics**: Join date, activity, download patterns
2. **Movie Analytics**: Popular movies, download counts
3. **Verification Analytics**: Success rates, patterns
4. **Search Analytics**: Popular queries, success rates

यह complete system आपकी सभी requirements को पूरा करता है - daily verification, file tracking, user management, और detailed analytics के साथ।