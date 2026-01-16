from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
import bcrypt
import json

db = SQLAlchemy()

class User(db.Model):
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    display_name = db.Column(db.String(120), nullable=True)
    password_hash = db.Column(db.String(200), nullable=False)
    bio = db.Column(db.Text, nullable=True)
    avatar_url = db.Column(db.String(500), nullable=True)
    banner_url = db.Column(db.String(500), nullable=True)
    is_admin = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_active = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Telegram fields
    telegram_id = db.Column(db.BigInteger, nullable=True, unique=True)
    telegram_username = db.Column(db.String(100), nullable=True)
    telegram_verified = db.Column(db.Boolean, default=False)
    
    # Email verification
    email_verified = db.Column(db.Boolean, default=True)
    verification_code = db.Column(db.String(10), nullable=True)
    verification_expires = db.Column(db.DateTime, nullable=True)
    
    # Music service tokens
    yandex_token = db.Column(db.Text, nullable=True)
    vk_token = db.Column(db.Text, nullable=True)
    spotify_token = db.Column(db.Text, nullable=True)
    
    # Social links
    vk_link = db.Column(db.String(200), nullable=True)
    telegram_link = db.Column(db.String(200), nullable=True)
    instagram_link = db.Column(db.String(200), nullable=True)
    
    # Preferences
    theme_preference = db.Column(db.String(50), default='dark')
    language = db.Column(db.String(10), default='ru')
    
    # Relationships
    currency = db.relationship('UserCurrency', backref='user', uselist=False, cascade='all, delete-orphan')
    settings = db.relationship('UserSettings', backref='user', uselist=False, cascade='all, delete-orphan')
    statistic = db.relationship('UserStatistic', backref='user', uselist=False, cascade='all, delete-orphan')
    inventory = db.relationship('UserInventory', backref='user', cascade='all, delete-orphan')
    activity = db.relationship('UserActivity', backref='user', cascade='all, delete-orphan')
    transactions = db.relationship('CurrencyTransaction', backref='user', cascade='all, delete-orphan')
    listening_history = db.relationship('ListeningHistory', backref='user', cascade='all, delete-orphan')
    friends = db.relationship('Friend', foreign_keys='Friend.user_id', backref='from_user', cascade='all, delete-orphan')
    friend_of = db.relationship('Friend', foreign_keys='Friend.friend_id', backref='to_user', cascade='all, delete-orphan')
    themes = db.relationship('UserTheme', backref='user', cascade='all, delete-orphan')
    api_logs = db.relationship('APILog', backref='user', cascade='all, delete-orphan')
    created_codes = db.relationship('TelegramCode', foreign_keys='TelegramCode.user_id', backref='user', cascade='all, delete-orphan')
    
    def set_password(self, password):
        self.password_hash = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
    
    def check_password(self, password):
        try:
            return bcrypt.checkpw(password.encode('utf-8'), self.password_hash.encode('utf-8'))
        except:
            return False
    
    def update_last_active(self):
        self.last_active = datetime.utcnow()
    
    def to_dict(self):
        return {
            'id': self.id,
            'username': self.username,
            'email': self.email,
            'display_name': self.display_name,
            'bio': self.bio,
            'avatar_url': self.avatar_url,
            'banner_url': self.banner_url,
            'is_admin': self.is_admin,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'last_active': self.last_active.isoformat() if self.last_active else None,
            'telegram_username': self.telegram_username,
            'telegram_verified': self.telegram_verified,
            'email_verified': self.email_verified,
            'has_yandex': bool(self.yandex_token),
            'has_vk': bool(self.vk_token),
            'has_spotify': bool(self.spotify_token),
            'theme': self.theme_preference,
            'language': self.language
        }

class ShopBanner(db.Model):
    __tablename__ = 'shop_banners'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=True)
    image_url = db.Column(db.String(500), nullable=False)
    preview_url = db.Column(db.String(500), nullable=True)
    price = db.Column(db.Integer, default=0)
    rarity = db.Column(db.String(50), default='common')
    category = db.Column(db.String(100), nullable=True)
    tags = db.Column(db.Text, nullable=True)  # JSON array
    is_active = db.Column(db.Boolean, default=True)
    is_featured = db.Column(db.Boolean, default=False)
    featured_order = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'image_url': self.image_url,
            'preview_url': self.preview_url,
            'price': self.price,
            'rarity': self.rarity,
            'category': self.category,
            'tags': json.loads(self.tags) if self.tags else [],
            'is_active': self.is_active,
            'is_featured': self.is_featured,
            'featured_order': self.featured_order,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }

class TelegramCode(db.Model):
    __tablename__ = 'telegram_codes'
    
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(50), nullable=False, unique=True)
    telegram_id = db.Column(db.BigInteger, nullable=True)
    telegram_username = db.Column(db.String(100), nullable=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    purpose = db.Column(db.String(50), nullable=False)  # 'registration', 'link_account', 'login'
    is_used = db.Column(db.Boolean, default=False)
    used_at = db.Column(db.DateTime, nullable=True)
    expires_at = db.Column(db.DateTime, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Additional data stored as JSON
    metadata = db.Column(db.Text, nullable=True)
    
    def to_dict(self):
        return {
            'id': self.id,
            'code': self.code,
            'telegram_id': self.telegram_id,
            'telegram_username': self.telegram_username,
            'user_id': self.user_id,
            'purpose': self.purpose,
            'is_used': self.is_used,
            'used_at': self.used_at.isoformat() if self.used_at else None,
            'expires_at': self.expires_at.isoformat(),
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'metadata': json.loads(self.metadata) if self.metadata else {}
        }

class TelegramSession(db.Model):
    __tablename__ = 'telegram_sessions'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    telegram_id = db.Column(db.BigInteger, nullable=False)
    chat_id = db.Column(db.BigInteger, nullable=False)
    username = db.Column(db.String(100), nullable=True)
    first_name = db.Column(db.String(100), nullable=True)
    last_name = db.Column(db.String(100), nullable=True)
    is_bot = db.Column(db.Boolean, default=False)
    session_data = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_active = db.Column(db.DateTime, default=datetime.utcnow)
    is_active = db.Column(db.Boolean, default=True)
    
    def to_dict(self):
        return {
            'id': self.id,
            'telegram_id': self.telegram_id,
            'username': self.username,
            'first_name': self.first_name,
            'last_name': self.last_name,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'is_active': self.is_active
        }

class UserCurrency(db.Model):
    __tablename__ = 'user_currency'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), unique=True, nullable=False)
    balance = db.Column(db.Integer, default=0)
    total_earned = db.Column(db.Integer, default=0)
    total_spent = db.Column(db.Integer, default=0)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def to_dict(self):
        return {
            'balance': self.balance,
            'total_earned': self.total_earned,
            'total_spent': self.total_spent,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }

class CurrencyTransaction(db.Model):
    __tablename__ = 'currency_transactions'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    amount = db.Column(db.Integer, nullable=False)
    reason = db.Column(db.String(100), nullable=False)
    transaction_metadata = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'amount': self.amount,
            'reason': self.reason,
            'metadata': json.loads(self.transaction_metadata) if self.transaction_metadata else {},
            'created_at': self.created_at.isoformat() if self.created_at else None
        }

class ShopCategory(db.Model):
    __tablename__ = 'shop_categories'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    description = db.Column(db.String(200), nullable=True)
    icon = db.Column(db.String(100), nullable=True)
    display_order = db.Column(db.Integer, default=0)
    is_active = db.Column(db.Boolean, default=True)
    parent_id = db.Column(db.Integer, db.ForeignKey('shop_categories.id'), nullable=True)
    color = db.Column(db.String(20), nullable=True)
    
    items = db.relationship('ShopItem', backref='category', cascade='all, delete-orphan')
    parent = db.relationship('ShopCategory', remote_side=[id], backref='subcategories')
    
    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'icon': self.icon,
            'display_order': self.display_order,
            'is_active': self.is_active,
            'parent_id': self.parent_id,
            'color': self.color,
            'item_count': self.items.filter_by(is_active=True).count()
        }

class ShopItem(db.Model):
    __tablename__ = 'shop_items'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=True)
    type = db.Column(db.String(50), nullable=False)
    category_id = db.Column(db.Integer, db.ForeignKey('shop_categories.id'), nullable=False)
    price = db.Column(db.Integer, nullable=False)
    original_price = db.Column(db.Integer, nullable=True)
    data = db.Column(db.Text, nullable=True)
    rarity = db.Column(db.String(50), default='common')
    stock = db.Column(db.Integer, default=-1)
    sales_count = db.Column(db.Integer, default=0)
    views_count = db.Column(db.Integer, default=0)
    is_active = db.Column(db.Boolean, default=True)
    is_featured = db.Column(db.Boolean, default=False)
    is_new = db.Column(db.Boolean, default=True)
    tags = db.Column(db.Text, nullable=True)  # JSON array
    image_url = db.Column(db.String(500), nullable=True)
    preview_url = db.Column(db.String(500), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    inventory = db.relationship('UserInventory', backref='item', cascade='all, delete-orphan')
    
    def get_data_dict(self):
        try:
            return json.loads(self.data) if self.data else {}
        except:
            return {}
    
    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'type': self.type,
            'category_id': self.category_id,
            'category_name': self.category.name if self.category else '',
            'price': self.price,
            'original_price': self.original_price,
            'data': self.get_data_dict(),
            'rarity': self.rarity,
            'stock': self.stock,
            'sales_count': self.sales_count,
            'views_count': self.views_count,
            'is_active': self.is_active,
            'is_featured': self.is_featured,
            'is_new': self.is_new,
            'tags': json.loads(self.tags) if self.tags else [],
            'image_url': self.image_url,
            'preview_url': self.preview_url,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }

class UserInventory(db.Model):
    __tablename__ = 'user_inventory'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    item_id = db.Column(db.Integer, db.ForeignKey('shop_items.id'), nullable=False)
    equipped = db.Column(db.Boolean, default=False)
    purchased_at = db.Column(db.DateTime, default=datetime.utcnow)
    expires_at = db.Column(db.DateTime, nullable=True)
    
    __table_args__ = (db.UniqueConstraint('user_id', 'item_id'),)
    
    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'item_id': self.item_id,
            'item_name': self.item.name if self.item else '',
            'equipped': self.equipped,
            'purchased_at': self.purchased_at.isoformat() if self.purchased_at else None,
            'expires_at': self.expires_at.isoformat() if self.expires_at else None
        }

class UserSettings(db.Model):
    __tablename__ = 'user_settings'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), unique=True, nullable=False)
    theme = db.Column(db.String(50), default='dark')
    language = db.Column(db.String(10), default='ru')
    auto_play = db.Column(db.Boolean, default=True)
    show_explicit = db.Column(db.Boolean, default=False)
    music_service = db.Column(db.String(20), default='yandex')
    notifications_enabled = db.Column(db.Boolean, default=True)
    privacy_level = db.Column(db.String(20), default='public')
    email_notifications = db.Column(db.Boolean, default=True)
    telegram_notifications = db.Column(db.Boolean, default=True)
    auto_renew_subscription = db.Column(db.Boolean, default=False)
    playback_quality = db.Column(db.String(20), default='high')
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def to_dict(self):
        return {
            'theme': self.theme,
            'language': self.language,
            'auto_play': self.auto_play,
            'show_explicit': self.show_explicit,
            'music_service': self.music_service,
            'notifications_enabled': self.notifications_enabled,
            'privacy_level': self.privacy_level,
            'email_notifications': self.email_notifications,
            'telegram_notifications': self.telegram_notifications,
            'auto_renew_subscription': self.auto_renew_subscription,
            'playback_quality': self.playback_quality,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }

class UserActivity(db.Model):
    __tablename__ = 'user_activity'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    activity_type = db.Column(db.String(100), nullable=False)
    activity_data = db.Column(db.Text, nullable=True)
    ip_address = db.Column(db.String(50), nullable=True)
    user_agent = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'activity_type': self.activity_type,
            'activity_data': json.loads(self.activity_data) if self.activity_data else {},
            'ip_address': self.ip_address,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }

class Friend(db.Model):
    __tablename__ = 'friends'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    friend_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    status = db.Column(db.String(20), default='pending')
    taste_match = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    __table_args__ = (db.UniqueConstraint('user_id', 'friend_id'),)
    
    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'friend_id': self.friend_id,
            'status': self.status,
            'taste_match': self.taste_match,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }

class ListeningHistory(db.Model):
    __tablename__ = 'listening_history'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    track_id = db.Column(db.String(100), nullable=False)
    track_data = db.Column(db.Text, nullable=True)
    service = db.Column(db.String(20), nullable=False)
    played_at = db.Column(db.DateTime, default=datetime.utcnow)
    duration = db.Column(db.Integer, default=0)
    
    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'track_id': self.track_id,
            'track_data': json.loads(self.track_data) if self.track_data else {},
            'service': self.service,
            'played_at': self.played_at.isoformat() if self.played_at else None,
            'duration': self.duration
        }

class UserTheme(db.Model):
    __tablename__ = 'user_themes'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    colors = db.Column(db.Text, nullable=False)
    background_url = db.Column(db.String(500), nullable=True)
    is_default = db.Column(db.Boolean, default=False)
    is_public = db.Column(db.Boolean, default=False)
    likes_count = db.Column(db.Integer, default=0)
    downloads_count = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'name': self.name,
            'colors': json.loads(self.colors),
            'background_url': self.background_url,
            'is_default': self.is_default,
            'is_public': self.is_public,
            'likes_count': self.likes_count,
            'downloads_count': self.downloads_count,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }

class CacheItem(db.Model):
    __tablename__ = 'cache_items'
    
    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(500), unique=True, nullable=False)
    value = db.Column(db.Text, nullable=False)
    expires_at = db.Column(db.DateTime, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': self.id,
            'key': self.key,
            'value': self.value[:100] + '...' if len(self.value) > 100 else self.value,
            'expires_at': self.expires_at.isoformat(),
            'created_at': self.created_at.isoformat() if self.created_at else None
        }

class UserStatistic(db.Model):
    __tablename__ = 'user_statistics'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), unique=True, nullable=False)
    tracks_listened = db.Column(db.Integer, default=0)
    minutes_listened = db.Column(db.Integer, default=0)
    items_purchased = db.Column(db.Integer, default=0)
    achievements_unlocked = db.Column(db.Integer, default=0)
    level = db.Column(db.Integer, default=1)
    xp = db.Column(db.Integer, default=0)
    daily_rewards_claimed = db.Column(db.Integer, default=0)
    last_daily_reward = db.Column(db.DateTime, nullable=True)
    last_login = db.Column(db.DateTime, nullable=True)
    total_logins = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def to_dict(self):
        return {
            'tracks_listened': self.tracks_listened,
            'minutes_listened': self.minutes_listened,
            'items_purchased': self.items_purchased,
            'achievements_unlocked': self.achievements_unlocked,
            'level': self.level,
            'xp': self.xp,
            'daily_rewards_claimed': self.daily_rewards_claimed,
            'last_daily_reward': self.last_daily_reward.isoformat() if self.last_daily_reward else None,
            'last_login': self.last_login.isoformat() if self.last_login else None,
            'total_logins': self.total_logins,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }

class APILog(db.Model):
    __tablename__ = 'api_logs'
    
    id = db.Column(db.Integer, primary_key=True)
    endpoint = db.Column(db.String(500), nullable=False)
    method = db.Column(db.String(10), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    ip_address = db.Column(db.String(50), nullable=True)
    status_code = db.Column(db.Integer, nullable=False)
    response_time = db.Column(db.Float, nullable=False)
    request_data = db.Column(db.Text, nullable=True)
    response_data = db.Column(db.Text, nullable=True)
    user_agent = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': self.id,
            'endpoint': self.endpoint,
            'method': self.method,
            'user_id': self.user_id,
            'ip_address': self.ip_address,
            'status_code': self.status_code,
            'response_time': self.response_time,
            'request_data': json.loads(self.request_data) if self.request_data else {},
            'user_agent': self.user_agent,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }