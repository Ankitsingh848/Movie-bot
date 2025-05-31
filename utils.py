import re
import logging
from typing import Dict, List, Optional
from fuzzywuzzy import fuzz, process

logger = logging.getLogger(__name__)

def format_file_size(size_bytes: int) -> str:
    """Convert bytes to human readable file size"""
    if size_bytes == 0:
        return "0 B"
    
    size_names = ["B", "KB", "MB", "GB", "TB"]
    i = 0
    
    while size_bytes >= 1024 and i < len(size_names) - 1:
        size_bytes /= 1024.0
        i += 1
    
    return f"{size_bytes:.1f} {size_names[i]}"

def parse_upload_caption(caption: str) -> Optional[Dict]:
    """Parse upload caption in format: Title | Year | Quality | Part/Season/Episode"""
    if not caption:
        return None
    
    try:
        # Split by pipe character and clean up
        parts = [part.strip() for part in caption.split("|")]
        
        if len(parts) < 3:
            return None
        
        title = parts[0]
        year_str = parts[1] if len(parts) > 1 else ""
        quality = parts[2] if len(parts) > 2 else ""
        part_season_episode = parts[3] if len(parts) > 3 else ""
        
        # Parse year
        year = None
        if year_str:
            year_match = re.search(r'\d{4}', year_str)
            if year_match:
                year = int(year_match.group())
        
        # Validate required fields
        if not title or not quality:
            return None
        
        return {
            'title': title,
            'year': year,
            'quality': quality,
            'part_season_episode': part_season_episode or "Complete"
        }
        
    except Exception as e:
        logger.error(f"Error parsing upload caption: {e}")
        return None

def fuzzy_search_movies(query: str, movies: List[Dict], threshold: int = 60) -> List[Dict]:
    """Perform fuzzy search on movies list"""
    if not movies:
        return []
    
    try:
        # Create searchable strings for each movie
        movie_strings = []
        for movie in movies:
            search_string = f"{movie['title']} {movie['quality']} {movie['part_season_episode']}"
            if movie['year']:
                search_string += f" {movie['year']}"
            movie_strings.append(search_string)
        
        # Perform fuzzy matching
        matches = process.extract(query, movie_strings, scorer=fuzz.partial_ratio, limit=len(movies))
        
        # Filter by threshold and sort by score
        filtered_results = []
        for match_result in matches:
            if len(match_result) == 3:
                match, score, index = match_result
            else:
                match, score = match_result
                index = movie_strings.index(match)
                
            if score >= threshold:
                movie = movies[index].copy()
                movie['search_score'] = score
                filtered_results.append(movie)
        
        # Sort by search score (highest first) and then by download count
        filtered_results.sort(key=lambda x: (x['search_score'], x['download_count']), reverse=True)
        
        return filtered_results
        
    except Exception as e:
        logger.error(f"Error in fuzzy search: {e}")
        return movies  # Return original list if fuzzy search fails

def clean_filename(filename: str) -> str:
    """Clean filename for safe storage"""
    # Remove or replace invalid characters
    cleaned = re.sub(r'[<>:"/\\|?*]', '_', filename)
    
    # Remove multiple consecutive underscores
    cleaned = re.sub(r'_+', '_', cleaned)
    
    # Remove leading/trailing underscores and spaces
    cleaned = cleaned.strip('_ ')
    
    return cleaned

def extract_movie_info_from_filename(filename: str) -> Dict:
    """Extract movie information from filename with smart auto-detection"""
    info = {
        'title': '',
        'year': None,
        'quality': 'HD',
        'part_season_episode': 'Complete'
    }
    
    try:
        # Remove file extension
        name_without_ext = re.sub(r'\.[^.]+$', '', filename)
        
        # Extract year
        year_match = re.search(r'\b(19|20)\d{2}\b', name_without_ext)
        if year_match:
            info['year'] = int(year_match.group())
            name_without_ext = name_without_ext.replace(year_match.group(), '', 1)
        
        # Extract quality
        quality_patterns = [
            r'\b(4K|2160p|1080p|720p|480p|360p)\b',
            r'\b(HD|FHD|UHD|SD)\b',
            r'\b(BluRay|BRRip|DVDRip|WEBRip|HDTV|CAMRip|DVDScr)\b'
        ]
        
        for pattern in quality_patterns:
            match = re.search(pattern, name_without_ext, re.IGNORECASE)
            if match:
                info['quality'] = match.group()
                name_without_ext = name_without_ext.replace(match.group(), '', 1)
                break
        
        if not info['quality']:
            info['quality'] = 'HD'  # Default quality
        
        # Extract season/episode/part info
        se_patterns = [
            r'\b(Season|S)[\s]*(\d+)[\s]*(Episode|E)[\s]*(\d+)\b',
            r'\bS(\d+)E(\d+)\b',
            r'\b(Part|Pt)[\s]*(\d+)\b',
            r'\b(Episode|Ep)[\s]*(\d+)\b'
        ]
        
        for pattern in se_patterns:
            match = re.search(pattern, name_without_ext, re.IGNORECASE)
            if match:
                info['part_season_episode'] = match.group()
                name_without_ext = name_without_ext.replace(match.group(), '', 1)
                break
        
        if not info['part_season_episode']:
            info['part_season_episode'] = 'Complete'  # Default
        
        # Clean up remaining text as title
        title = re.sub(r'[._\-\[\]()]', ' ', name_without_ext)
        title = re.sub(r'\s+', ' ', title).strip()
        
        # Remove common release group tags and extra info
        title = re.sub(r'\b(x264|x265|AAC|DTS|AC3|MP3|5\.1|7\.1|RARBG|YTS|YIFY)\b', '', title, flags=re.IGNORECASE)
        title = re.sub(r'\s+', ' ', title).strip()
        
        info['title'] = title if title else filename
        
        return info
        
    except Exception as e:
        logger.error(f"Error extracting movie info from filename: {e}")
        return info

def validate_search_query(query: str) -> bool:
    """Validate search query"""
    if not query or len(query.strip()) < 2:
        return False
    
    # Check for only special characters
    if re.match(r'^[^a-zA-Z0-9]+$', query.strip()):
        return False
    
    return True

def sanitize_text(text: str) -> str:
    """Sanitize text for safe display"""
    if not text:
        return ""
    
    # Remove HTML tags
    text = re.sub(r'<[^>]+>', '', text)
    
    # Remove excessive whitespace
    text = re.sub(r'\s+', ' ', text)
    
    return text.strip()

def format_duration(seconds: int) -> str:
    """Format duration in seconds to human readable format"""
    if seconds < 60:
        return f"{seconds}s"
    elif seconds < 3600:
        minutes = seconds // 60
        remaining_seconds = seconds % 60
        return f"{minutes}m {remaining_seconds}s"
    else:
        hours = seconds // 3600
        remaining_minutes = (seconds % 3600) // 60
        return f"{hours}h {remaining_minutes}m"

def is_admin(user_id: int) -> bool:
    """Check if user is an admin"""
    from config import Config
    return user_id in Config.ADMIN_IDS

def truncate_text(text: str, max_length: int = 100) -> str:
    """Truncate text to specified length"""
    if len(text) <= max_length:
        return text
    return text[:max_length-3] + "..."

def create_progress_bar(current: int, total: int, length: int = 20) -> str:
    """Create a progress bar string"""
    if total == 0:
        return "█" * length
    
    filled_length = int(length * current / total)
    bar = "█" * filled_length + "░" * (length - filled_length)
    percentage = round(100.0 * current / total, 1)
    
    return f"{bar} {percentage}%"
