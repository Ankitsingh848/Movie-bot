"""
Database models for Auto Filter Movie Bot
"""

import os
from datetime import datetime, timedelta
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import DeclarativeBase

class Base(DeclarativeBase):
    pass

db = SQLAlchemy(model_class=Base)

class User(db.Model):
    """User information table"""
    __tablename__ = 'users'
    
    user_id = db.Column(db.BigInteger, primary_key=True)
    username = db.Column(db.String(255), nullable=True)
    first_name = db.Column(db.String(255), nullable=True)
    last_name = db.Column(db.String(255), nullable=True)
    is_banned = db.Column(db.Boolean, default=False)
    is_premium = db.Column(db.Boolean, default=False)
    join_date = db.Column(db.DateTime, default=datetime.utcnow)
    last_active = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Daily verification status
    last_verified = db.Column(db.DateTime, nullable=True)
    verification_count = db.Column(db.Integer, default=0)
    
    def is_verified_today(self):
        """Check if user is verified for today (24 hours)"""
        if not self.last_verified:
            return False
        return datetime.utcnow() - self.last_verified < timedelta(hours=24)
    
    def mark_verified(self):
        """Mark user as verified for today"""
        self.last_verified = datetime.utcnow()
        self.verification_count += 1

class Movie(db.Model):
    """Movie files table"""
    __tablename__ = 'movies'
    
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(500), nullable=False)
    year = db.Column(db.Integer, nullable=True)
    quality = db.Column(db.String(50), nullable=True)
    language = db.Column(db.String(50), default='Hindi')
    genre = db.Column(db.String(200), nullable=True)
    
    # File information
    file_id = db.Column(db.String(200), unique=True, nullable=False)
    file_name = db.Column(db.String(500), nullable=False)
    file_size = db.Column(db.BigInteger, default=0)
    file_type = db.Column(db.String(50), nullable=True)  # video, document
    
    # Upload information
    uploaded_by = db.Column(db.BigInteger, nullable=False)
    upload_date = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Statistics
    download_count = db.Column(db.Integer, default=0)
    search_count = db.Column(db.Integer, default=0)
    
    # Status
    is_active = db.Column(db.Boolean, default=True)
    is_featured = db.Column(db.Boolean, default=False)

class UserVerification(db.Model):
    """Daily verification tracking"""
    __tablename__ = 'user_verifications'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.BigInteger, nullable=False)
    movie_id = db.Column(db.Integer, nullable=False)
    
    # Verification details
    verification_token = db.Column(db.String(100), unique=True, nullable=False)
    short_url = db.Column(db.String(500), nullable=False)
    original_url = db.Column(db.String(500), nullable=False)
    
    # Timing
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    expires_at = db.Column(db.DateTime, nullable=False)
    verified_at = db.Column(db.DateTime, nullable=True)
    
    # Status
    is_verified = db.Column(db.Boolean, default=False)
    is_expired = db.Column(db.Boolean, default=False)
    
    @property
    def is_valid(self):
        """Check if verification is still valid"""
        return not self.is_expired and datetime.utcnow() < self.expires_at

class DownloadLog(db.Model):
    """Download tracking table"""
    __tablename__ = 'download_logs'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.BigInteger, nullable=False)
    movie_id = db.Column(db.Integer, nullable=False)
    
    # Download details
    download_method = db.Column(db.String(50), default='telegram')  # telegram, direct
    file_sent = db.Column(db.Boolean, default=False)
    
    # Timing
    requested_at = db.Column(db.DateTime, default=datetime.utcnow)
    completed_at = db.Column(db.DateTime, nullable=True)
    
    # Auto-delete system
    auto_delete_time = db.Column(db.DateTime, nullable=True)
    is_deleted = db.Column(db.Boolean, default=False)

class SearchLog(db.Model):
    """Search query tracking"""
    __tablename__ = 'search_logs'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.BigInteger, nullable=False)
    query = db.Column(db.String(500), nullable=False)
    results_count = db.Column(db.Integer, default=0)
    search_date = db.Column(db.DateTime, default=datetime.utcnow)

class URLShortener(db.Model):
    """URL shortening service tracking"""
    __tablename__ = 'url_shorteners'
    
    id = db.Column(db.Integer, primary_key=True)
    original_url = db.Column(db.String(1000), nullable=False)
    short_url = db.Column(db.String(500), nullable=False)
    short_code = db.Column(db.String(100), unique=True, nullable=False)
    
    # Usage tracking
    click_count = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    expires_at = db.Column(db.DateTime, nullable=True)
    
    # Associated with verification
    verification_id = db.Column(db.Integer, db.ForeignKey('user_verifications.id'), nullable=True)

class BotSettings(db.Model):
    """Bot configuration settings"""
    __tablename__ = 'bot_settings'
    
    id = db.Column(db.Integer, primary_key=True)
    setting_key = db.Column(db.String(100), unique=True, nullable=False)
    setting_value = db.Column(db.Text, nullable=False)
    description = db.Column(db.String(500), nullable=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow)

class AdminAction(db.Model):
    """Admin actions log"""
    __tablename__ = 'admin_actions'
    
    id = db.Column(db.Integer, primary_key=True)
    admin_id = db.Column(db.BigInteger, nullable=False)
    action_type = db.Column(db.String(100), nullable=False)  # upload, delete, ban, etc.
    target_id = db.Column(db.String(100), nullable=True)  # user_id, movie_id, etc.
    details = db.Column(db.Text, nullable=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)