"""
Daily Verification System for Auto Filter Movie Bot
"""

import uuid
import hashlib
import aiohttp
from datetime import datetime, timedelta
from models import db, User, UserVerification, DownloadLog, URLShortener
from config import Config
import logging

logger = logging.getLogger(__name__)

class VerificationSystem:
    """Handles daily user verification through shortened URLs"""
    
    def __init__(self):
        self.api_key = Config.INSHORT_API_KEY
        self.api_url = Config.INSHORT_API_URL
    
    async def check_user_verification_status(self, user_id: int) -> dict:
        """
        Check if user needs verification today
        Returns: {
            'needs_verification': bool,
            'last_verified': datetime or None,
            'hours_remaining': int
        }
        """
        user = User.query.filter_by(user_id=user_id).first()
        
        if not user:
            # New user - needs verification
            return {
                'needs_verification': True,
                'last_verified': None,
                'hours_remaining': 24
            }
        
        if user.is_verified_today():
            # User is verified for today
            time_diff = datetime.utcnow() - user.last_verified
            hours_remaining = 24 - int(time_diff.total_seconds() / 3600)
            return {
                'needs_verification': False,
                'last_verified': user.last_verified,
                'hours_remaining': max(0, hours_remaining)
            }
        else:
            # User needs verification
            return {
                'needs_verification': True,
                'last_verified': user.last_verified,
                'hours_remaining': 24
            }
    
    async def create_verification_request(self, user_id: int, movie_id: int) -> dict:
        """
        Create new verification request with unique token and short URL
        Returns: {
            'verification_token': str,
            'short_url': str,
            'expires_at': datetime
        }
        """
        # Generate unique verification token
        verification_token = self._generate_verification_token(user_id, movie_id)
        
        # Create original URL for verification
        original_url = f"https://t.me/{Config.BOT_USERNAME}?start=verify_{verification_token}"
        
        # Create short URL
        short_url = await self._create_short_url(original_url, verification_token)
        
        # Set expiration (24 hours from now)
        expires_at = datetime.utcnow() + timedelta(hours=24)
        
        # Save verification request to database
        verification = UserVerification(
            user_id=user_id,
            movie_id=movie_id,
            verification_token=verification_token,
            short_url=short_url,
            original_url=original_url,
            expires_at=expires_at
        )
        
        db.session.add(verification)
        db.session.commit()
        
        logger.info(f"Created verification request for user {user_id}, movie {movie_id}")
        
        return {
            'verification_token': verification_token,
            'short_url': short_url,
            'expires_at': expires_at,
            'verification_id': verification.id
        }
    
    async def verify_user_by_token(self, verification_token: str) -> dict:
        """
        Verify user when they come from shortened URL
        Returns: {
            'success': bool,
            'user_id': int,
            'movie_id': int,
            'message': str
        }
        """
        verification = UserVerification.query.filter_by(
            verification_token=verification_token,
            is_verified=False
        ).first()
        
        if not verification:
            return {
                'success': False,
                'user_id': None,
                'movie_id': None,
                'message': 'Invalid या expired verification link'
            }
        
        if not verification.is_valid:
            verification.is_expired = True
            db.session.commit()
            return {
                'success': False,
                'user_id': verification.user_id,
                'movie_id': verification.movie_id,
                'message': 'Verification link expired. कृपया नया link generate करें।'
            }
        
        # Mark verification as completed
        verification.is_verified = True
        verification.verified_at = datetime.utcnow()
        
        # Update user verification status
        user = User.query.filter_by(user_id=verification.user_id).first()
        if not user:
            user = User(user_id=verification.user_id)
            db.session.add(user)
        
        user.mark_verified()
        
        db.session.commit()
        
        logger.info(f"User {verification.user_id} verified successfully for movie {verification.movie_id}")
        
        return {
            'success': True,
            'user_id': verification.user_id,
            'movie_id': verification.movie_id,
            'message': '✅ Verification successful! आपकी फाइल भेजी जा रही है...'
        }
    
    async def _create_short_url(self, original_url: str, verification_token: str) -> str:
        """Create shortened URL using InShort API"""
        try:
            async with aiohttp.ClientSession() as session:
                data = {
                    'url': original_url,
                    'api': self.api_key
                }
                
                async with session.post(self.api_url, data=data) as response:
                    if response.status == 200:
                        result = await response.json()
                        if result.get('status') == 'success':
                            short_url = result.get('shortenedUrl')
                            
                            # Save URL mapping
                            url_shortener = URLShortener(
                                original_url=original_url,
                                short_url=short_url,
                                short_code=verification_token[:10],
                                expires_at=datetime.utcnow() + timedelta(hours=24)
                            )
                            db.session.add(url_shortener)
                            
                            return short_url
            
            # Fallback if API fails
            return f"https://short.link/{verification_token[:8]}"
            
        except Exception as e:
            logger.error(f"URL shortening failed: {e}")
            return f"https://t.me/{Config.BOT_USERNAME}?start=verify_{verification_token}"
    
    def _generate_verification_token(self, user_id: int, movie_id: int) -> str:
        """Generate unique verification token"""
        timestamp = datetime.utcnow().timestamp()
        unique_string = f"{user_id}_{movie_id}_{timestamp}_{uuid.uuid4().hex[:8]}"
        
        # Create hash
        token = hashlib.md5(unique_string.encode()).hexdigest()
        return token
    
    async def get_verification_stats(self) -> dict:
        """Get verification statistics"""
        total_verifications = UserVerification.query.count()
        successful_verifications = UserVerification.query.filter_by(is_verified=True).count()
        pending_verifications = UserVerification.query.filter_by(is_verified=False).count()
        expired_verifications = UserVerification.query.filter_by(is_expired=True).count()
        
        # Today's stats
        today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        today_verifications = UserVerification.query.filter(
            UserVerification.created_at >= today_start
        ).count()
        
        return {
            'total_verifications': total_verifications,
            'successful_verifications': successful_verifications,
            'pending_verifications': pending_verifications,
            'expired_verifications': expired_verifications,
            'today_verifications': today_verifications,
            'success_rate': (successful_verifications / total_verifications * 100) if total_verifications > 0 else 0
        }
    
    async def cleanup_expired_verifications(self):
        """Clean up expired verification requests"""
        expired_verifications = UserVerification.query.filter(
            UserVerification.expires_at < datetime.utcnow(),
            UserVerification.is_verified == False
        ).all()
        
        for verification in expired_verifications:
            verification.is_expired = True
        
        db.session.commit()
        
        logger.info(f"Marked {len(expired_verifications)} verifications as expired")
        return len(expired_verifications)
    
    async def get_user_verification_history(self, user_id: int, limit: int = 10) -> list:
        """Get user's verification history"""
        verifications = UserVerification.query.filter_by(
            user_id=user_id
        ).order_by(
            UserVerification.created_at.desc()
        ).limit(limit).all()
        
        history = []
        for v in verifications:
            history.append({
                'verification_id': v.id,
                'movie_id': v.movie_id,
                'created_at': v.created_at,
                'verified_at': v.verified_at,
                'is_verified': v.is_verified,
                'is_expired': v.is_expired,
                'short_url': v.short_url
            })
        
        return history