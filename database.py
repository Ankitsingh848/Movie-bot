import sqlite3
import json
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
from contextlib import contextmanager

logger = logging.getLogger(__name__)

class Database:
    """Database manager for the movie bot"""
    
    def __init__(self, db_path: str = "movie_bot.db"):
        self.db_path = db_path
        
    @contextmanager
    def get_connection(self):
        """Context manager for database connections"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        except Exception as e:
            conn.rollback()
            logger.error(f"Database error: {e}")
            raise
        finally:
            conn.close()
    
    def init_db(self):
        """Initialize database tables"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Movies table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS movies (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    year INTEGER,
                    quality TEXT,
                    part_season_episode TEXT,
                    file_id TEXT NOT NULL,
                    file_name TEXT NOT NULL,
                    file_size INTEGER,
                    original_url TEXT,
                    shortened_url TEXT,
                    upload_date DATETIME DEFAULT CURRENT_TIMESTAMP,
                    uploaded_by INTEGER NOT NULL,
                    download_count INTEGER DEFAULT 0,
                    last_accessed DATETIME,
                    is_active BOOLEAN DEFAULT 1
                )
            """)
            
            # Search logs table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS search_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    username TEXT,
                    search_query TEXT NOT NULL,
                    results_count INTEGER DEFAULT 0,
                    search_date DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Download logs table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS download_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    username TEXT,
                    movie_id INTEGER NOT NULL,
                    download_date DATETIME DEFAULT CURRENT_TIMESTAMP,
                    auto_delete_date DATETIME,
                    FOREIGN KEY (movie_id) REFERENCES movies (id)
                )
            """)
            
            # Verification requests table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS verification_requests (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    movie_id INTEGER NOT NULL,
                    token TEXT NOT NULL,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    status TEXT DEFAULT 'pending'
                )
            """)
            
            # User verifications table for daily verification tracking
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS user_verifications (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL UNIQUE,
                    verified_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    verification_count INTEGER DEFAULT 1,
                    dm_accessible BOOLEAN DEFAULT 1
                )
            """)
            
            # Rate limiting table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS rate_limits (
                    user_id INTEGER PRIMARY KEY,
                    last_search DATETIME,
                    search_count INTEGER DEFAULT 0,
                    last_upload DATETIME,
                    upload_count INTEGER DEFAULT 0
                )
            """)
            
            # User verification tracking table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS user_verifications (
                    user_id INTEGER PRIMARY KEY,
                    last_verification DATETIME,
                    dm_accessible BOOLEAN DEFAULT FALSE
                )
            """)
            
            # URL visit tracking table for proper verification
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS url_visits (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    movie_id INTEGER NOT NULL,
                    shortened_url TEXT NOT NULL,
                    verification_token TEXT NOT NULL,
                    visit_time DATETIME,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (movie_id) REFERENCES movies (id)
                )
            """)
            
            # Movie requests table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS movie_requests (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    username TEXT,
                    movie_name TEXT NOT NULL,
                    request_date DATETIME DEFAULT CURRENT_TIMESTAMP,
                    status TEXT DEFAULT 'pending'
                )
            """)
            
            # User messages log for admin monitoring
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS user_messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    username TEXT,
                    message_text TEXT NOT NULL,
                    message_date DATETIME DEFAULT CURRENT_TIMESTAMP,
                    message_type TEXT DEFAULT 'text'
                )
            """)
            
            # Multi-step verification tracking
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS verification_steps (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    movie_id INTEGER NOT NULL,
                    step_number INTEGER NOT NULL,
                    completed_at DATETIME,
                    verification_url TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(user_id, movie_id, step_number),
                    FOREIGN KEY (movie_id) REFERENCES movies (id)
                )
            """)
            
            # Create indexes for better performance
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_movies_title ON movies(title)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_search_logs_user_date ON search_logs(user_id, search_date)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_download_logs_auto_delete ON download_logs(auto_delete_date)")
            
            conn.commit()
            logger.info("Database initialized successfully")
    
    def add_movie(self, title: str, year: Optional[int], quality: str, 
                  part_season_episode: str, file_id: str, file_name: str, 
                  file_size: int, original_url: str, shortened_url: str, 
                  uploaded_by: int) -> int:
        """Add a new movie to the database"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO movies 
                (title, year, quality, part_season_episode, file_id, file_name, 
                 file_size, original_url, shortened_url, uploaded_by)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (title, year, quality, part_season_episode, file_id, file_name,
                  file_size, original_url, shortened_url, uploaded_by))
            
            movie_id = cursor.lastrowid
            conn.commit()
            
            logger.info(f"Added movie: {title} (ID: {movie_id})")
            return movie_id
    
    def search_movies(self, query: str, limit: int = 10) -> List[Dict]:
        """Search for movies using the query"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Search in title, quality, and part_season_episode fields
            search_pattern = f"%{query}%"
            cursor.execute("""
                SELECT * FROM movies 
                WHERE is_active = 1 AND (
                    title LIKE ? OR 
                    quality LIKE ? OR 
                    part_season_episode LIKE ?
                )
                ORDER BY 
                    CASE 
                        WHEN title LIKE ? THEN 1
                        WHEN title LIKE ? THEN 2
                        ELSE 3
                    END,
                    download_count DESC,
                    upload_date DESC
                LIMIT ?
            """, (search_pattern, search_pattern, search_pattern,
                  f"{query}%", search_pattern, limit))
            
            results = []
            for row in cursor.fetchall():
                results.append({
                    'id': row['id'],
                    'title': row['title'],
                    'year': row['year'],
                    'quality': row['quality'],
                    'part_season_episode': row['part_season_episode'],
                    'file_id': row['file_id'],
                    'file_name': row['file_name'],
                    'file_size': row['file_size'],
                    'shortened_url': row['shortened_url'],
                    'download_count': row['download_count'],
                    'upload_date': row['upload_date']
                })
            
            return results
    
    def get_movie_by_id(self, movie_id: int) -> Optional[Dict]:
        """Get a movie by its ID"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM movies WHERE id = ? AND is_active = 1", (movie_id,))
            row = cursor.fetchone()
            
            if row:
                return {
                    'id': row['id'],
                    'title': row['title'],
                    'year': row['year'],
                    'quality': row['quality'],
                    'part_season_episode': row['part_season_episode'],
                    'file_id': row['file_id'],
                    'file_name': row['file_name'],
                    'file_size': row['file_size'],
                    'shortened_url': row['shortened_url'],
                    'download_count': row['download_count']
                }
            return None
    
    def increment_download_count(self, movie_id: int):
        """Increment the download count for a movie"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE movies 
                SET download_count = download_count + 1, last_accessed = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (movie_id,))
            conn.commit()
    
    def log_search(self, user_id: int, username: str, query: str, results_count: int):
        """Log a search query"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO search_logs (user_id, username, search_query, results_count)
                VALUES (?, ?, ?, ?)
            """, (user_id, username, query, results_count))
            conn.commit()
    
    def log_download(self, user_id: int, username: str, movie_id: int, auto_delete_minutes: int):
        """Log a download with auto-delete timestamp"""
        auto_delete_date = datetime.now() + timedelta(minutes=auto_delete_minutes)
        
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO download_logs (user_id, username, movie_id, auto_delete_date)
                VALUES (?, ?, ?, ?)
            """, (user_id, username, movie_id, auto_delete_date))
            conn.commit()
    
    def get_files_to_delete(self) -> List[Dict]:
        """Get files that should be auto-deleted"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT dl.*, m.file_id, m.title 
                FROM download_logs dl
                JOIN movies m ON dl.movie_id = m.id
                WHERE dl.auto_delete_date <= CURRENT_TIMESTAMP
                AND dl.auto_delete_date IS NOT NULL
            """)
            
            results = []
            for row in cursor.fetchall():
                results.append({
                    'download_id': row['id'],
                    'user_id': row['user_id'],
                    'movie_id': row['movie_id'],
                    'file_id': row['file_id'],
                    'title': row['title'],
                    'auto_delete_date': row['auto_delete_date']
                })
            
            return results
    
    def mark_file_deleted(self, download_id: int):
        """Mark a file as deleted in download logs"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE download_logs 
                SET auto_delete_date = NULL 
                WHERE id = ?
            """, (download_id,))
            conn.commit()
    
    def check_user_verification(self, user_id: int) -> bool:
        """Check if user has verified within last 24 hours"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                # Ensure table exists with correct schema
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS user_verifications (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id INTEGER NOT NULL UNIQUE,
                        verified_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                        verification_count INTEGER DEFAULT 1,
                        dm_accessible BOOLEAN DEFAULT 1
                    )
                """)
                
                cursor.execute("""
                    SELECT verified_at FROM user_verifications 
                    WHERE user_id = ? AND datetime(verified_at, '+24 hours') > datetime('now')
                """, (user_id,))
                
                result = cursor.fetchone()
                return result is not None
        except Exception as e:
            logger.error(f"Database error: {e}")
            return False
    
    def mark_user_verified(self, user_id: int, dm_accessible: bool = True):
        """Mark user as verified for 24 hours"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                # Ensure table exists with correct schema
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS user_verifications (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id INTEGER NOT NULL UNIQUE,
                        verified_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                        verification_count INTEGER DEFAULT 1,
                        dm_accessible BOOLEAN DEFAULT 1
                    )
                """)
                
                cursor.execute("""
                    INSERT OR REPLACE INTO user_verifications 
                    (user_id, verified_at, dm_accessible)
                    VALUES (?, datetime('now'), ?)
                """, (user_id, dm_accessible))
                conn.commit()
        except Exception as e:
            logger.error(f"Database error: {e}")
    
    def check_dm_accessible(self, user_id: int) -> bool:
        """Check if user's DM is accessible"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT dm_accessible FROM user_verifications 
                WHERE user_id = ?
            """, (user_id,))
            
            result = cursor.fetchone()
            return result[0] if result else False
    
    def save_user_info(self, user_id: int, username: str, first_name: str):
        """Save or update user information in database"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                # Ensure users table exists
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS users (
                        id INTEGER PRIMARY KEY,
                        user_id INTEGER NOT NULL UNIQUE,
                        username TEXT,
                        first_name TEXT,
                        last_seen DATETIME DEFAULT CURRENT_TIMESTAMP,
                        join_date DATETIME DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                # Insert or update user info
                cursor.execute("""
                    INSERT OR REPLACE INTO users 
                    (user_id, username, first_name, last_seen, join_date)
                    VALUES (?, ?, ?, datetime('now'), 
                            COALESCE((SELECT join_date FROM users WHERE user_id = ?), datetime('now')))
                """, (user_id, username, first_name, user_id))
                
                conn.commit()
                logger.info(f"Saved user info: {user_id} ({username})")
                
        except Exception as e:
            logger.error(f"Error saving user info: {e}")
    
    def check_rate_limit(self, user_id: int, action: str) -> bool:
        """Check if user is within rate limits"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            now = datetime.now()
            
            if action == "search":
                # Check search rate limit (5 per minute)
                minute_ago = now - timedelta(minutes=1)
                cursor.execute("""
                    SELECT search_count FROM rate_limits 
                    WHERE user_id = ? AND last_search > ?
                """, (user_id, minute_ago))
                
                result = cursor.fetchone()
                if result and result['search_count'] >= 5:
                    return False
                
                # Update rate limit
                cursor.execute("""
                    INSERT OR REPLACE INTO rate_limits 
                    (user_id, last_search, search_count)
                    VALUES (?, ?, COALESCE((
                        SELECT CASE 
                            WHEN last_search > ? THEN search_count + 1 
                            ELSE 1 
                        END
                        FROM rate_limits WHERE user_id = ?
                    ), 1))
                """, (user_id, now, minute_ago, user_id))
                
            elif action == "upload":
                # Check upload rate limit (10 per hour)
                hour_ago = now - timedelta(hours=1)
                cursor.execute("""
                    SELECT upload_count FROM rate_limits 
                    WHERE user_id = ? AND last_upload > ?
                """, (user_id, hour_ago))
                
                result = cursor.fetchone()
                if result and result['upload_count'] >= 10:
                    return False
                
                # Update rate limit
                cursor.execute("""
                    INSERT OR REPLACE INTO rate_limits 
                    (user_id, last_upload, upload_count)
                    VALUES (?, ?, COALESCE((
                        SELECT CASE 
                            WHEN last_upload > ? THEN upload_count + 1 
                            ELSE 1 
                        END
                        FROM rate_limits WHERE user_id = ?
                    ), 1))
                """, (user_id, now, hour_ago, user_id))
            
            conn.commit()
            return True
    
    def get_stats(self) -> Dict:
        """Get bot statistics"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Total movies
            cursor.execute("SELECT COUNT(*) as count FROM movies WHERE is_active = 1")
            total_movies = cursor.fetchone()['count']
            
            # Total downloads
            cursor.execute("SELECT COUNT(*) as count FROM download_logs")
            total_downloads = cursor.fetchone()['count']
            
            # Total searches
            cursor.execute("SELECT COUNT(*) as count FROM search_logs")
            total_searches = cursor.fetchone()['count']
            
            # Unique users
            cursor.execute("SELECT COUNT(DISTINCT user_id) as count FROM search_logs")
            unique_users = cursor.fetchone()['count']
            
            # Popular movies
            cursor.execute("""
                SELECT title, download_count 
                FROM movies 
                WHERE is_active = 1 
                ORDER BY download_count DESC 
                LIMIT 5
            """)
            popular_movies = cursor.fetchall()
            
            return {
                'total_movies': total_movies,
                'total_downloads': total_downloads,
                'total_searches': total_searches,
                'unique_users': unique_users,
                'popular_movies': [dict(movie) for movie in popular_movies]
            }
    
    def create_verification_request(self, user_id: int, movie_id: int, shortened_url: str) -> str:
        """Create a verification request and return a unique token"""
        import uuid
        verification_token = str(uuid.uuid4())
        
        with self.get_connection() as conn:
            cursor = conn.cursor()
            # Remove any existing verification requests for this user
            cursor.execute("DELETE FROM url_visits WHERE user_id = ?", (user_id,))
            
            # Create new verification request
            cursor.execute("""
                INSERT INTO url_visits 
                (user_id, movie_id, shortened_url, verification_token)
                VALUES (?, ?, ?, ?)
            """, (user_id, movie_id, shortened_url, verification_token))
            conn.commit()
            
        return verification_token
    
    def verify_url_visit(self, user_id: int, movie_id: int) -> bool:
        """Check if user can be verified (time-based verification)"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Check if there's a verification request that's at least 5 seconds old
            cursor.execute("""
                SELECT verification_token, created_at FROM url_visits 
                WHERE user_id = ? AND movie_id = ? AND visit_time IS NULL
                AND created_at <= datetime('now', '-5 seconds')
                ORDER BY created_at DESC LIMIT 1
            """, (user_id, movie_id))
            
            result = cursor.fetchone()
            if not result:
                return False
            
            # Mark as visited if enough time has passed
            cursor.execute("""
                UPDATE url_visits 
                SET visit_time = datetime('now')
                WHERE user_id = ? AND movie_id = ? AND visit_time IS NULL
            """, (user_id, movie_id))
            conn.commit()
            return True
    
    def has_recent_url_visit(self, user_id: int, movie_id: int) -> bool:
        """Check if user has visited URL recently (within last 5 minutes)"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT 1 FROM url_visits 
                WHERE user_id = ? AND movie_id = ? 
                AND visit_time IS NOT NULL 
                AND visit_time > datetime('now', '-5 minutes')
            """, (user_id, movie_id))
            
            return cursor.fetchone() is not None
    
    def log_user_message(self, user_id: int, username: str, message_text: str, message_type: str = 'text'):
        """Log user messages for admin monitoring"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO user_messages (user_id, username, message_text, message_type)
                VALUES (?, ?, ?, ?)
            """, (user_id, username, message_text, message_type))
            conn.commit()
    
    def add_movie_request(self, user_id: int, username: str, movie_name: str):
        """Add a movie request from user"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO movie_requests (user_id, username, movie_name)
                VALUES (?, ?, ?)
            """, (user_id, username, movie_name))
            conn.commit()
    
    def reset_all_verifications(self):
        """Reset all user verifications (admin function)"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM user_verifications")
            cursor.execute("DELETE FROM url_visits")
            cursor.execute("DELETE FROM verification_steps")
            conn.commit()
    
    def get_recent_user_messages(self, limit: int = 50) -> List[Dict]:
        """Get recent user messages for admin monitoring"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT user_id, username, message_text, message_type, message_date
                FROM user_messages 
                ORDER BY message_date DESC 
                LIMIT ?
            """, (limit,))
            
            return [dict(row) for row in cursor.fetchall()]
    
    def get_movie_requests(self, status: str = 'pending') -> List[Dict]:
        """Get movie requests by status"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, user_id, username, movie_name, request_date, status
                FROM movie_requests 
                WHERE status = ?
                ORDER BY request_date DESC
            """, (status,))
            
            return [dict(row) for row in cursor.fetchall()]
    
    def start_multi_step_verification(self, user_id: int, movie_id: int) -> int:
        """Start 4-step verification process"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            # Clear any existing verification for this user-movie combination
            cursor.execute("DELETE FROM verification_steps WHERE user_id = ? AND movie_id = ?", 
                         (user_id, movie_id))
            
            # Create 4 verification steps
            for step in range(1, 5):
                cursor.execute("""
                    INSERT INTO verification_steps (user_id, movie_id, step_number)
                    VALUES (?, ?, ?)
                """, (user_id, movie_id, step))
            
            conn.commit()
            return 4  # Return total steps
    
    def complete_verification_step(self, user_id: int, movie_id: int, step_number: int) -> bool:
        """Complete a verification step"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE verification_steps 
                SET completed_at = datetime('now')
                WHERE user_id = ? AND movie_id = ? AND step_number = ?
                AND completed_at IS NULL
            """, (user_id, movie_id, step_number))
            
            conn.commit()
            return cursor.rowcount > 0
    
    def get_verification_status(self, user_id: int, movie_id: int) -> Dict:
        """Get current verification status for user-movie"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT step_number, completed_at 
                FROM verification_steps 
                WHERE user_id = ? AND movie_id = ?
                ORDER BY step_number
            """, (user_id, movie_id))
            
            steps = cursor.fetchall()
            if not steps:
                return {'total_steps': 0, 'completed_steps': 0, 'current_step': 1}
            
            completed_count = sum(1 for step in steps if step['completed_at'] is not None)
            current_step = completed_count + 1 if completed_count < len(steps) else len(steps)
            
            return {
                'total_steps': len(steps),
                'completed_steps': completed_count,
                'current_step': current_step,
                'is_complete': completed_count == len(steps)
            }
    
    def get_all_users_for_broadcast(self) -> List[int]:
        """Get all user IDs for broadcasting messages"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT DISTINCT user_id FROM search_logs")
            return [row['user_id'] for row in cursor.fetchall()]
