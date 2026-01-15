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
    telegram_code = db.Column(db.String(10), nullable=True)
    telegram_code_expires = db.Column(db.DateTime, nullable=True)
    
    # Email verification (now optional)
    email_verified = db.Column(db.Boolean, default=True)
    
    # Music service tokens
    yandex_token = db.Column(db.Text, nullable=True)
    vk_token = db.Column(db.Text, nullable=True)
    
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
    
    def set_password(self, password):
        self.password_hash = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
    
    def check_password(self, password):
        return bcrypt.checkpw(password.encode('utf-8'), self.password_hash.encode('utf-8'))
    
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
            'has_vk': bool(self.vk_token)
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

class CurrencyTransaction(db.Model):
    __tablename__ = 'currency_transactions'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    amount = db.Column(db.Integer, nullable=False)
    reason = db.Column(db.String(100), nullable=False)
    transaction_metadata = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class ShopCategory(db.Model):
    __tablename__ = 'shop_categories'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    description = db.Column(db.String(200), nullable=True)
    icon = db.Column(db.String(100), nullable=True)
    display_order = db.Column(db.Integer, default=0)
    is_active = db.Column(db.Boolean, default=True)
    
    items = db.relationship('ShopItem', backref='category', cascade='all, delete-orphan')

class ShopItem(db.Model):
    __tablename__ = 'shop_items'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    type = db.Column(db.String(50), nullable=False)
    category_id = db.Column(db.Integer, db.ForeignKey('shop_categories.id'), nullable=False)
    price = db.Column(db.Integer, nullable=False)
    data = db.Column(db.Text, nullable=True)
    rarity = db.Column(db.String(50), default='common')
    stock = db.Column(db.Integer, default=-1)
    sales_count = db.Column(db.Integer, default=0)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    inventory = db.relationship('UserInventory', backref='item', cascade='all, delete-orphan')
    
    def get_data_dict(self):
        try:
            return json.loads(self.data) if self.data else {}
        except:
            return {}

class UserInventory(db.Model):
    __tablename__ = 'user_inventory'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    item_id = db.Column(db.Integer, db.ForeignKey('shop_items.id'), nullable=False)
    equipped = db.Column(db.Boolean, default=False)
    purchased_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    __table_args__ = (db.UniqueConstraint('user_id', 'item_id'),)

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
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class UserActivity(db.Model):
    __tablename__ = 'user_activity'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    activity_type = db.Column(db.String(100), nullable=False)
    activity_data = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

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

class ListeningHistory(db.Model):
    __tablename__ = 'listening_history'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    track_id = db.Column(db.String(100), nullable=False)
    track_data = db.Column(db.Text, nullable=True)
    service = db.Column(db.String(20), nullable=False)
    played_at = db.Column(db.DateTime, default=datetime.utcnow)

class UserTheme(db.Model):
    __tablename__ = 'user_themes'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    colors = db.Column(db.Text, nullable=False)
    background_url = db.Column(db.String(500), nullable=True)
    is_default = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class CacheItem(db.Model):
    __tablename__ = 'cache_items'
    
    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(500), unique=True, nullable=False)
    value = db.Column(db.Text, nullable=False)
    expires_at = db.Column(db.DateTime, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

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
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class APILog(db.Model):
    __tablename__ = 'api_logs'
    
    id = db.Column(db.Integer, primary_key=True)
    endpoint = db.Column(db.String(500), nullable=False)
    method = db.Column(db.String(10), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    ip_address = db.Column(db.String(50), nullable=True)
    status_code = db.Column(db.Integer, nullable=False)
    response_time = db.Column(db.Float, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)