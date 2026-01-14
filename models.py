from datetime import datetime, timedelta
from flask_sqlalchemy import SQLAlchemy
import bcrypt
import json

db = SQLAlchemy()

# --- Вспомогательные функции ---
def generate_hash(password):
    """Генерация хэша пароля"""
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

def check_hash(password, hashed):
    """Проверка хэша пароля"""
    return bcrypt.checkpw(password.encode('utf-8'), hashed.encode('utf-8'))

# --- Модели ---
class User(db.Model):
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    display_name = db.Column(db.String(100), nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    avatar_url = db.Column(db.String(500), default='/static/default-avatar.png')
    bio = db.Column(db.Text, default='')
    is_admin = db.Column(db.Boolean, default=False)
    email_verified = db.Column(db.Boolean, default=False)
    verification_code = db.Column(db.String(10))
    verification_code_expires = db.Column(db.DateTime)
    yandex_token = db.Column(db.Text)
    vk_token = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_active = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Связи
    settings = db.relationship('UserSettings', backref='user', uselist=False, cascade='all, delete-orphan')
    currency = db.relationship('UserCurrency', backref='user', uselist=False, cascade='all, delete-orphan')
    inventory = db.relationship('UserInventory', backref='user', cascade='all, delete-orphan')
    transactions = db.relationship('CurrencyTransaction', backref='user', cascade='all, delete-orphan')
    activities = db.relationship('UserActivity', backref='user', cascade='all, delete-orphan')
    statistics = db.relationship('UserStatistic', backref='user', uselist=False, cascade='all, delete-orphan')
    history = db.relationship('ListeningHistory', backref='user', cascade='all, delete-orphan')
    friends_sent = db.relationship('Friend', foreign_keys='Friend.user_id', backref='from_user', cascade='all, delete-orphan')
    friends_received = db.relationship('Friend', foreign_keys='Friend.friend_id', backref='to_user', cascade='all, delete-orphan')
    themes = db.relationship('UserTheme', backref='user', cascade='all, delete-orphan')
    
    def set_password(self, password):
        self.password_hash = generate_hash(password)
    
    def check_password(self, password):
        return check_hash(password, self.password_hash)
    
    def update_last_active(self):
        self.last_active = datetime.utcnow()
    
    def to_dict(self):
        return {
            'id': self.id,
            'username': self.username,
            'email': self.email,
            'display_name': self.display_name,
            'avatar_url': self.avatar_url,
            'bio': self.bio,
            'is_admin': self.is_admin,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'last_active': self.last_active.isoformat() if self.last_active else None,
            'has_yandex': bool(self.yandex_token),
            'has_vk': bool(self.vk_token)
        }

class UserCurrency(db.Model):
    __tablename__ = 'user_currencies'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), unique=True, nullable=False)
    balance = db.Column(db.Integer, default=0)
    total_earned = db.Column(db.Integer, default=0)
    total_spent = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class CurrencyTransaction(db.Model):
    __tablename__ = 'currency_transactions'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    amount = db.Column(db.Integer, nullable=False)
    reason = db.Column(db.String(100), nullable=False)
    # Изменили 'metadata' на 'transaction_metadata'
    transaction_metadata = db.Column(db.Text, nullable=True, default='{}')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def get_metadata(self):
        try:
            return json.loads(self.transaction_metadata) if self.transaction_metadata else {}
        except:
            return {}

class ShopCategory(db.Model):
    __tablename__ = 'shop_categories'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False)
    description = db.Column(db.String(200))
    icon = db.Column(db.String(50))
    display_order = db.Column(db.Integer, default=0)
    is_active = db.Column(db.Boolean, default=True)
    
    items = db.relationship('ShopItem', backref='category', lazy='dynamic')

class ShopItem(db.Model):
    __tablename__ = 'shop_items'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    type = db.Column(db.String(50), nullable=False)  # theme, avatar, banner, badge, effect, animation
    category_id = db.Column(db.Integer, db.ForeignKey('shop_categories.id'), nullable=False)
    price = db.Column(db.Integer, nullable=False)
    data = db.Column(db.Text, nullable=False, default='{}')
    rarity = db.Column(db.String(20), default='common')  # common, rare, epic, legendary
    stock = db.Column(db.Integer, default=-1)  # -1 = unlimited
    sales_count = db.Column(db.Integer, default=0)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    inventory_items = db.relationship('UserInventory', backref='item', cascade='all, delete-orphan')
    
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
    
    __table_args__ = (db.UniqueConstraint('user_id', 'item_id', name='unique_user_item'),)

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
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class UserActivity(db.Model):
    __tablename__ = 'user_activities'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    activity_type = db.Column(db.String(50), nullable=False)  # login, purchase, listen, etc.
    description = db.Column(db.String(500))
    ip_address = db.Column(db.String(50))
    user_agent = db.Column(db.String(500))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Friend(db.Model):
    __tablename__ = 'friends'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    friend_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    status = db.Column(db.String(20), default='pending')  # pending, accepted, rejected, blocked
    taste_match = db.Column(db.Float, default=0.0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    __table_args__ = (db.UniqueConstraint('user_id', 'friend_id', name='unique_friendship'),)

class ListeningHistory(db.Model):
    __tablename__ = 'listening_history'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    track_id = db.Column(db.String(100), nullable=False)
    track_data = db.Column(db.Text)
    service = db.Column(db.String(20), nullable=False)  # yandex, vk
    played_at = db.Column(db.DateTime, default=datetime.utcnow)

class UserTheme(db.Model):
    __tablename__ = 'user_themes'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    colors = db.Column(db.Text, nullable=False)  # JSON с цветами
    background_url = db.Column(db.String(500))
    is_default = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class CacheItem(db.Model):
    __tablename__ = 'cache_items'
    
    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(255), unique=True, nullable=False)
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
    daily_rewards_claimed = db.Column(db.Integer, default=0)
    last_daily_reward = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class APILog(db.Model):
    __tablename__ = 'api_logs'
    
    id = db.Column(db.Integer, primary_key=True)
    endpoint = db.Column(db.String(500), nullable=False)
    method = db.Column(db.String(10), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    ip_address = db.Column(db.String(50))
    status_code = db.Column(db.Integer, nullable=False)
    response_time = db.Column(db.Float, default=0.0)  # в миллисекундах
    created_at = db.Column(db.DateTime, default=datetime.utcnow)