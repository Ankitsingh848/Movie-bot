import aiohttp
import logging
from typing import Optional
from config import Config

logger = logging.getLogger(__name__)

class URLShortener:
    """URL shortener service using inshorturl.com"""
    
    def __init__(self):
        self.api_token = Config.INSHORT_API_TOKEN or Config.INSHORT_API_KEY
        self.api_url = "https://inshorturl.com/api"
        
    async def shorten_url(self, original_url: str) -> Optional[str]:
        """Shorten a URL using inshorturl.com service"""
        if not self.api_token:
            logger.error("INSHORT_API_KEY not configured")
            return original_url  # Return original URL as fallback
        
        try:
            # URL encode the original URL
            from urllib.parse import quote
            encoded_url = quote(original_url, safe='')
            
            # Build API URL as per your specification
            api_request_url = f"{self.api_url}?api={self.api_token}&url={encoded_url}&format=text"
            
            headers = {
                'User-Agent': 'TelegramMovieBot/1.0'
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    api_request_url,
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=30)
                ) as response:
                    
                    if response.status == 200:
                        shortened_url = await response.text()
                        shortened_url = shortened_url.strip()
                        
                        if shortened_url and shortened_url.startswith('http'):
                            logger.info(f"URL shortened successfully: {original_url} -> {shortened_url}")
                            return shortened_url
                        else:
                            logger.error(f"API returned invalid response: {shortened_url}")
                    else:
                        logger.error(f"HTTP error {response.status}: {await response.text()}")
                        
        except Exception as e:
            logger.error(f"Error while shortening URL: {e}")
        
        # Return original URL if shortening fails
        logger.warning(f"URL shortening failed, returning original URL: {original_url}")
        return original_url
    
    async def expand_url(self, short_url: str) -> Optional[str]:
        """Expand a shortened URL (if needed for verification)"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.head(
                    short_url,
                    allow_redirects=True,
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as response:
                    return str(response.url)
                    
        except Exception as e:
            logger.error(f"Error expanding URL {short_url}: {e}")
            return None
    
    async def verify_shortened_url(self, short_url: str) -> bool:
        """Verify that a shortened URL is accessible"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.head(
                    short_url,
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as response:
                    return response.status < 400
                    
        except Exception as e:
            logger.error(f"Error verifying URL {short_url}: {e}")
            return False
    
    async def get_url_stats(self, short_url: str) -> Optional[dict]:
        """Get statistics for a shortened URL (if supported by the service)"""
        # This would depend on the specific API capabilities of inshort.url
        # For now, return None as this feature might not be available
        try:
            stats_payload = {
                'url': short_url,
                'api_key': self.api_key,
                'action': 'stats'
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.api_url.replace('/shorten', '/stats'),
                    json=stats_payload,
                    timeout=aiohttp.ClientTimeout(total=15)
                ) as response:
                    
                    if response.status == 200:
                        data = await response.json()
                        if data.get('success'):
                            return {
                                'clicks': data.get('clicks', 0),
                                'created_date': data.get('created_date'),
                                'last_click': data.get('last_click')
                            }
                            
        except Exception as e:
            logger.error(f"Error getting URL stats: {e}")
        
        return None
    
    async def batch_shorten_urls(self, urls: list) -> dict:
        """Shorten multiple URLs in batch"""
        results = {}
        
        for original_url in urls:
            shortened = await self.shorten_url(original_url)
            results[original_url] = shortened
        
        return results
    
    def is_shortened_url(self, url: str) -> bool:
        """Check if a URL appears to be a shortened URL"""
        shortened_domains = [
            'inshort.url',
            'bit.ly',
            'tinyurl.com',
            'short.link',
            't.co',
            'goo.gl'
        ]
        
        return any(domain in url.lower() for domain in shortened_domains)
