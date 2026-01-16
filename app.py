from flask import Flask, render_template, jsonify, request, session, redirect, url_for, send_from_directory, send_file
from flask_migrate import Migrate
from flask_caching import Cache
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_cors import CORS
from models import db, User, UserCurrency, ShopCategory, ShopItem, UserInventory, TelegramSession
from models import CurrencyTransaction, UserSettings, UserActivity, Friend, ListeningHistory, UserTheme
from models import CacheItem, UserStatistic, APILog, ShopBanner, TelegramCode
from utils import login_required, admin_required, add_currency, recommender, cache_response
from utils import send_verification_email, save_uploaded_file, get_yandex_client, get_vk_client
from utils import log_api_request, get_api_stats, cache_db_set, cache_db_get, clean_expired_cache
from utils import get_yandex_client_cached, get_vk_client_cached, redis_client, send_telegram_message
from utils import validate_image, rate_limit_by_user, invalidate_cache
import os
import secrets
from datetime import datetime, timedelta
import logging
import bcrypt
import uuid
import json
import base64
from io import BytesIO
import time
from functools import wraps
import random
import asyncio
import threading

# Импортируем Telegram бота
from telegram_bot import init_telegram_bot, telegram_bot, stop_telegram_bot

# Определяем базовую директорию
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Создаем папки для логов и загрузок перед настройкой логирования
logs_dir = os.path.join(BASE_DIR, 'logs')
avatars_dir = os.path.join(BASE_DIR, 'static', 'uploads', 'avatars')
banners_dir = os.path.join(BASE_DIR, 'static', 'uploads', 'banners')
shop_items_dir = os.path.join(BASE_DIR, 'static', 'uploads', 'shop_items')
music_covers_dir = os.path.join(BASE_DIR, 'static', 'uploads', 'covers')

os.makedirs(logs_dir, exist_ok=True)
os.makedirs(avatars_dir, exist_ok=True)
os.makedirs(banners_dir, exist_ok=True)
os.makedirs(shop_items_dir, exist_ok=True)
os.makedirs(music_covers_dir, exist_ok=True)

# Настройка логирования с абсолютным путем
log_file = os.path.join(logs_dir, 'app.log')
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_file),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Создание приложения
app = Flask(__name__, static_folder='static')
app.secret_key = os.getenv('SECRET_KEY', secrets.token_hex(32))
app.permanent_session_lifetime = timedelta(days=30)

# CORS
CORS(app, resources={r"/api/*": {"origins": "*"}})

# Конфигурация базы данных
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL', 'sqlite:///itired.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
    'pool_recycle': 300,
    'pool_pre_ping': True,
    'pool_size': 10,
    'max_overflow': 20,
}

# Конфигурация загрузки файлов
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB
app.config['UPLOAD_FOLDER'] = 'static/uploads'
app.config['ALLOWED_EXTENSIONS'] = {'png', 'jpg', 'jpeg', 'gif', 'webp', 'mp3', 'wav', 'ogg'}

# Инициализация расширений
db.init_app(app)
migrate = Migrate(app, db)

# Кэширование
cache_config = {
    'CACHE_TYPE': os.getenv('CACHE_TYPE', 'SimpleCache'),
    'CACHE_DEFAULT_TIMEOUT': 300,
    'CACHE_KEY_PREFIX': 'itired_'
}

if os.getenv('REDIS_URL'):
    cache_config['CACHE_TYPE'] = 'RedisCache'
    cache_config['CACHE_REDIS_URL'] = os.getenv('REDIS_URL')

cache = Cache(app, config=cache_config)

# Rate limiting
limiter = Limiter(
    app=app,
    key_func=get_remote_address,
    default_limits=[os.getenv('RATE_LIMIT_DEFAULT', "200 per day, 50 per hour")],
    storage_uri="memory://",
    strategy="fixed-window"
)

# Флаг для отслеживания инициализации
app_initialized = False

# Инициализация при первом запросе (замена before_first_request)
@app.before_request
def initialize_on_first_request():
    global app_initialized
    if not app_initialized:
        with app.app_context():
            try:
                # Создаем таблицы
                db.create_all()
                
                # Инициализируем данные
                init_shop_data()
                create_admin_user()
                
                # Очищаем просроченный кэш
                clean_expired_cache()
                
                # Очищаем старые Telegram коды
                clean_old_telegram_codes()
                
                # Инициализируем Telegram бота (если токен есть)
                telegram_token = os.getenv('TELEGRAM_BOT_TOKEN')
                run_bot = os.getenv('RUN_TELEGRAM_BOT', 'true').lower() == 'true'
                
                if telegram_token and run_bot:
                    try:
                        init_telegram_bot(telegram_token)
                        logger.info("Telegram bot initialized successfully")
                    except Exception as e:
                        logger.error(f"Failed to initialize Telegram bot: {e}")
                else:
                    logger.info("Telegram bot disabled (no token or RUN_TELEGRAM_BOT=false)")
                
                app_initialized = True
                logger.info("Приложение инициализировано успешно")
            except Exception as e:
                logger.error(f"Ошибка инициализации: {e}")

def init_shop_data():
    """Инициализация магазина начальными данными"""
    try:
        # Создаем категории
        categories = [
            ('themes', 'Темы оформления', 'fas fa-palette', 1),
            ('avatars', 'Аватары', 'fas fa-user', 2),
            ('banners', 'Баннеры профиля', 'fas fa-image', 3),
            ('badges', 'Бейджи', 'fas fa-medal', 4),
            ('effects', 'Эффекты плеера', 'fas fa-magic', 5),
            ('animations', 'Анимации', 'fas fa-film', 6),
            ('music', 'Музыка', 'fas fa-music', 7),
            ('stickers', 'Стикеры', 'fas fa-sticker-mule', 8),
            ('frames', 'Рамки профиля', 'fas fa-square', 9),
            ('titles', 'Титулы', 'fas fa-crown', 10)
        ]
        
        for cat_name, cat_desc, cat_icon, order in categories:
            category = ShopCategory.query.filter_by(name=cat_name).first()
            if not category:
                category = ShopCategory(
                    name=cat_name,
                    description=cat_desc,
                    icon=cat_icon,
                    display_order=order,
                    is_active=True
                )
                db.session.add(category)
        
        db.session.commit()
        
        # Создаем несколько стандартных товаров
        default_items = [
            ('Темная тема Premium', 'theme', 'themes', 100, 
             '{"styles": {"--bg-primary": "#0a0a0a", "--bg-secondary": "#141414", "--accent": "#ff6b6b", "--text-primary": "#ffffff"}}', 'epic'),
            
            ('Синяя тема Ocean', 'theme', 'themes', 75,
             '{"styles": {"--bg-primary": "#0a1929", "--bg-secondary": "#132f4c", "--accent": "#1976d2", "--text-primary": "#e3f2fd"}}', 'rare'),
            
            ('Аватар "Звезда"', 'avatar', 'avatars', 30,
             '{"image_url": "/static/default/avatar_star.png", "animated": false}', 'common'),
            
            ('Аватар "Лунный свет"', 'avatar', 'avatars', 45,
             '{"image_url": "/static/default/avatar_moon.png", "animated": true}', 'rare'),
            
            ('Баннер "Горизонт"', 'profile_banner', 'banners', 120,
             '{"image_url": "/static/default/banner_horizon.jpg", "preview": "/static/default/banner_horizon.jpg"}', 'rare'),
            
            ('Бейдж "VIP"', 'badge', 'badges', 200,
             '{"text": "⭐ VIP", "color": "#ffd700", "animation": "glow"}', 'epic'),
            
            ('Эффект "Неоновое сияние"', 'effect', 'effects', 150,
             '{"css": ".player { filter: drop-shadow(0 0 10px #ff00ff); }", "duration": 30000}', 'legendary')
        ]
        
        for name, item_type, category_name, price, data, rarity in default_items:
            category = ShopCategory.query.filter_by(name=category_name).first()
            if category:
                item = ShopItem.query.filter_by(name=name).first()
                if not item:
                    item = ShopItem(
                        name=name,
                        type=item_type,
                        category_id=category.id,
                        price=price,
                        data=data,
                        rarity=rarity,
                        stock=10,
                        is_active=True
                    )
                    db.session.add(item)
        
        db.session.commit()
        logger.info("Данные магазина инициализированы")
        
    except Exception as e:
        logger.error(f"Ошибка инициализации магазина: {e}")

def create_admin_user():
    try:
        admin_user = User.query.filter_by(username='admin').first()
        if not admin_user:
            admin_user = User(
                username='admin',
                email='admin@itired.com',
                display_name='Администратор',
                is_admin=True,
                email_verified=True
            )
            admin_user.set_password('admin123')
            db.session.add(admin_user)
            db.session.commit()
            
            # Создаем настройки для админа
            settings = UserSettings(user_id=admin_user.id)
            db.session.add(settings)
            
            # Создаем валюту для админа
            currency = UserCurrency(user_id=admin_user.id, balance=10000)
            db.session.add(currency)
            
            # Создаем статистику
            stats = UserStatistic(user_id=admin_user.id)
            db.session.add(stats)
            
            db.session.commit()
            logger.info("Администратор создан: admin / admin123")
    except Exception as e:
        logger.error(f"Ошибка создания администратора: {e}")

def clean_old_telegram_codes():
    """Очистка старых Telegram кодов"""
    try:
        from models import TelegramCode
        expired = TelegramCode.query.filter(
            TelegramCode.expires_at <= datetime.utcnow()
        ).all()
        
        for code in expired:
            db.session.delete(code)
        
        db.session.commit()
        logger.info(f"Удалено {len(expired)} просроченных Telegram кодов")
    except Exception as e:
        logger.error(f"Ошибка очистки Telegram кодов: {e}")

# --- Декоратор для логирования API ---
def api_logged(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        start_time = time.time()
        try:
            response = f(*args, **kwargs)
            elapsed = (time.time() - start_time) * 1000  # в миллисекундах
            
            # Логируем запрос
            log_api_request(
                endpoint=request.path,
                method=request.method,
                user_id=session.get('user_id'),
                status_code=200,
                response_time=elapsed
            )
            
            return response
        except Exception as e:
            elapsed = (time.time() - start_time) * 1000
            status_code = 500 if not hasattr(e, 'code') else e.code
            
            log_api_request(
                endpoint=request.path,
                method=request.method,
                user_id=session.get('user_id'),
                status_code=status_code,
                response_time=elapsed
            )
            
            raise e
    return decorated_function

# --- Основные маршруты ---
@app.route('/')
def index():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
@limiter.limit("10 per minute")
def login():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        
        user = User.query.filter((User.username == username) | (User.email == username)).first()
        
        if user and user.check_password(password):
            session.permanent = True
            session['user_id'] = user.id
            session['username'] = user.username
            
            # Обновляем время последней активности
            user.update_last_active()
            db.session.commit()
            
            return redirect(url_for('index'))
        
        return render_template('auth.html', mode='login', error='Неверные данные')
    
    return render_template('auth.html', mode='login')

@app.route('/register', methods=['GET', 'POST'])
@limiter.limit("5 per minute")
def register():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        confirm_password = request.form.get('confirm_password', '')
        telegram_code = request.form.get('telegram_code', '').strip().upper()
        
        # Telegram регистрация
        if telegram_code:
            return handle_telegram_registration(username, email, password, confirm_password, telegram_code)
        
        # Старая регистрация
        if not all([username, email, password, confirm_password]):
            return render_template('auth.html', mode='register', error='Все поля обязательны')
        
        if password != confirm_password:
            return render_template('auth.html', mode='register', error='Пароли не совпадают')
        
        if len(password) < 6:
            return render_template('auth.html', mode='register', error='Пароль должен быть не менее 6 символов')
        
        # Проверка существующего пользователя
        existing = User.query.filter((User.username == username) | (User.email == email)).first()
        if existing:
            return render_template('auth.html', mode='register', error='Пользователь уже существует')
        
        # Создаем пользователя
        user = User(
            username=username,
            email=email,
            display_name=username or username,
            email_verified=True
        )
        user.set_password(password)
        
        db.session.add(user)
        db.session.commit()
        
        # Создаем настройки по умолчанию
        settings = UserSettings(user_id=user.id)
        db.session.add(settings)
        
        # Создаем начальную валюту
        currency = UserCurrency(user_id=user.id, balance=100)
        db.session.add(currency)
        
        # Создаем статистику
        stats = UserStatistic(user_id=user.id)
        db.session.add(stats)
        
        db.session.commit()
        
        # Авторизуем пользователя
        session.permanent = True
        session['user_id'] = user.id
        session['username'] = user.username
        
        return redirect(url_for('index'))
    
    return render_template('auth.html', mode='register')

def handle_telegram_registration(username, email, password, confirm_password, telegram_code):
    """Обработка регистрации через Telegram"""
    # Проверяем код
    telegram_code_obj = TelegramCode.query.filter_by(
        code=telegram_code,
        is_used=False
    ).first()
    
    if not telegram_code_obj:
        return render_template('auth.html', mode='register', error='Неверный код Telegram')
    
    if telegram_code_obj.expires_at < datetime.utcnow():
        return render_template('auth.html', mode='register', error='Код истек')
    
    # Проверка данных
    if not all([username, email, password, confirm_password]):
        return render_template('auth.html', mode='register', error='Все поля обязательны')
    
    if password != confirm_password:
        return render_template('auth.html', mode='register', error='Пароли не совпадают')
    
    if len(password) < 6:
        return render_template('auth.html', mode='register', error='Пароль должен быть не менее 6 символов')
    
    # Проверка существующего пользователя
    existing = User.query.filter((User.username == username) | (User.email == email)).first()
    if existing:
        return render_template('auth.html', mode='register', error='Пользователь уже существует')
    
    # Создаем пользователя с привязкой Telegram
    user = User(
        username=username,
        email=email,
        display_name=username or telegram_code_obj.telegram_username,
        email_verified=True,
        telegram_id=telegram_code_obj.telegram_id,
        telegram_username=telegram_code_obj.telegram_username,
        telegram_verified=True
    )
    user.set_password(password)
    
    db.session.add(user)
    
    # Помечаем код как использованный
    telegram_code_obj.is_used = True
    telegram_code_obj.used_at = datetime.utcnow()
    telegram_code_obj.user_id = user.id
    
    # Создаем настройки по умолчанию
    settings = UserSettings(user_id=user.id)
    db.session.add(settings)
    
    # Создаем начальную валюту (бонус за регистрацию через Telegram)
    currency = UserCurrency(user_id=user.id, balance=200)
    db.session.add(currency)
    
    # Создаем статистику
    stats = UserStatistic(user_id=user.id)
    db.session.add(stats)
    
    db.session.commit()
    
    # Отправляем приветственное сообщение в Telegram
    if telegram_code_obj.telegram_id:
        try:
            send_telegram_message(
                telegram_code_obj.telegram_id,
                f"🎉 *Регистрация успешна!*\n\n"
                f"Добро пожаловать в itired, {username}!\n"
                f"На твой счет начислено 200 монет (бонус за регистрацию через Telegram) 💰\n\n"
                f"Твой профиль: {request.host_url}profile/{username}\n\n"
                f"Для управления аккаунтом используй команды:\n"
                f"/start - меню бота\n"
                f"/profile - твой профиль\n"
                f"/balance - баланс монет"
            )
        except Exception as e:
            logger.error(f"Failed to send welcome message to Telegram: {e}")
    
    # Авторизуем пользователя
    session.permanent = True
    session['user_id'] = user.id
    session['username'] = user.username
    
    return redirect(url_for('index'))

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

# --- Telegram API маршруты ---
@app.route('/api/telegram/generate_code', methods=['POST'])
@login_required
@api_logged
def generate_telegram_code():
    """Генерация кода для привязки Telegram"""
    user = User.query.get(session['user_id'])
    
    if user.telegram_id:
        return jsonify({'success': False, 'message': 'Telegram уже привязан'})
    
    # Генерируем уникальный код
    code = ''.join(random.choices('0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ', k=8))
    expires_at = datetime.utcnow() + timedelta(minutes=15)
    
    # Сохраняем код в базе
    telegram_code = TelegramCode(
        code=code,
        user_id=user.id,
        expires_at=expires_at,
        purpose='link_account'
    )
    db.session.add(telegram_code)
    db.session.commit()
    
    return jsonify({
        'success': True,
        'code': code,
        'expires_at': expires_at.isoformat(),
        'instructions': 'Отправь этот код боту @itired_music_bot для привязки аккаунта'
    })

@app.route('/api/telegram/check_link')
@login_required
@api_logged
def check_telegram_link():
    """Проверить, привязан ли Telegram"""
    user = User.query.get(session['user_id'])
    
    return jsonify({
        'linked': bool(user.telegram_id),
        'telegram_username': user.telegram_username,
        'telegram_verified': user.telegram_verified
    })

@app.route('/api/telegram/link_with_code', methods=['POST'])
@login_required
@api_logged
def link_telegram_with_code():
    """Привязка Telegram с кодом"""
    user = User.query.get(session['user_id'])
    data = request.get_json()
    
    code = data.get('code', '').strip().upper()
    
    if not code:
        return jsonify({'success': False, 'message': 'Введите код'})
    
    # Ищем код
    telegram_code = TelegramCode.query.filter_by(
        code=code,
        is_used=False,
        purpose='link_account'
    ).first()
    
    if not telegram_code:
        return jsonify({'success': False, 'message': 'Неверный код'})
    
    if telegram_code.expires_at < datetime.utcnow():
        return jsonify({'success': False, 'message': 'Код истек'})
    
    if telegram_code.user_id != user.id:
        return jsonify({'success': False, 'message': 'Код не для вашего аккаунта'})
    
    # Привязываем Telegram
    user.telegram_id = telegram_code.telegram_id
    user.telegram_username = telegram_code.telegram_username
    user.telegram_verified = True
    
    # Помечаем код как использованный
    telegram_code.is_used = True
    telegram_code.used_at = datetime.utcnow()
    
    db.session.commit()
    
    return jsonify({
        'success': True,
        'message': 'Telegram успешно привязан',
        'telegram_username': user.telegram_username
    })

@app.route('/api/telegram/unlink', methods=['POST'])
@login_required
@api_logged
def unlink_telegram():
    """Отвязка Telegram аккаунта"""
    user = User.query.get(session['user_id'])
    
    user.telegram_id = None
    user.telegram_username = None
    user.telegram_verified = False
    
    db.session.commit()
    
    return jsonify({'success': True, 'message': 'Telegram отвязан'})

# --- API маршруты для профиля и магазина ---
@app.route('/api/profile')
@login_required
@api_logged
def get_profile_api():
    user = User.query.get(session['user_id'])
    if not user:
        return jsonify({'error': 'Пользователь не найден'}), 404
    
    return jsonify({
        'user': user.to_dict(),
        'balance': user.currency.balance if user.currency else 0,
        'stats': {
            'tracks_listened': user.statistic.tracks_listened if user.statistic else 0,
            'items_purchased': user.statistic.items_purchased if user.statistic else 0,
            'level': user.statistic.level if user.statistic else 1
        },
        'settings': user.settings.to_dict() if user.settings else {}
    })

@app.route('/api/profile', methods=['PUT'])
@login_required
@api_logged
def update_profile():
    user = User.query.get(session['user_id'])
    if not user:
        return jsonify({'error': 'Пользователь не найден'}), 404
    
    data = request.get_json() or request.form
    
    if 'display_name' in data:
        user.display_name = data['display_name'].strip()[:100]
    
    if 'bio' in data:
        user.bio = data['bio'].strip()[:500]
    
    # Обработка аватара
    if 'avatar' in data and data['avatar']:
        try:
            if data['avatar'].startswith('data:image/'):
                header, encoded = data['avatar'].split(',', 1)
                file_data = base64.b64decode(encoded)
                
                saved_path = save_uploaded_file(file_data, 'avatar')
                if saved_path:
                    user.avatar_url = saved_path
            elif data['avatar'].startswith(('http://', 'https://')):
                user.avatar_url = data['avatar']
        except Exception as e:
            logger.error(f"Avatar update error: {e}")
    
    # Обработка баннера
    if 'banner' in data and data['banner']:
        try:
            if data['banner'].startswith('data:image/'):
                header, encoded = data['banner'].split(',', 1)
                file_data = base64.b64decode(encoded)
                
                saved_path = save_uploaded_file(file_data, 'banner')
                if saved_path:
                    user.banner_url = saved_path
            elif data['banner'].startswith(('http://', 'https://')):
                user.banner_url = data['banner']
        except Exception as e:
            logger.error(f"Banner update error: {e}")
    
    db.session.commit()
    
    return jsonify({'success': True, 'message': 'Профиль обновлен', 'user': user.to_dict()})

# Магазин
@app.route('/api/shop/categories')
@login_required
@cache.cached(timeout=3600)
@api_logged
def get_shop_categories():
    categories = ShopCategory.query.filter_by(is_active=True).order_by(ShopCategory.display_order).all()
    return jsonify([{
        'id': cat.id,
        'name': cat.name,
        'description': cat.description,
        'icon': cat.icon,
        'item_count': cat.items.filter_by(is_active=True).count()
    } for cat in categories])

@app.route('/api/shop/items')
@login_required
@cache_response(timeout=300)
@api_logged
def get_shop_items():
    category_id = request.args.get('category_id', type=int)
    rarity = request.args.get('rarity')
    min_price = request.args.get('min_price', type=int)
    max_price = request.args.get('max_price', type=int)
    type_filter = request.args.get('type')
    
    query = ShopItem.query.filter_by(is_active=True)
    
    if category_id:
        query = query.filter_by(category_id=category_id)
    
    if rarity:
        query = query.filter_by(rarity=rarity)
    
    if type_filter:
        query = query.filter_by(type=type_filter)
    
    if min_price is not None:
        query = query.filter(ShopItem.price >= min_price)
    
    if max_price is not None:
        query = query.filter(ShopItem.price <= max_price)
    
    items = query.order_by(ShopItem.created_at.desc()).all()
    user = User.query.get(session['user_id'])
    owned_item_ids = [inv.item_id for inv in user.inventory]
    
    result = []
    for item in items:
        result.append({
            'id': item.id,
            'name': item.name,
            'type': item.type,
            'category': item.category.name if item.category else '',
            'category_id': item.category_id,
            'price': item.price,
            'rarity': item.rarity,
            'data': item.get_data_dict(),
            'owned': item.id in owned_item_ids,
            'stock': item.stock,
            'sales_count': item.sales_count,
            'is_active': item.is_active
        })
    
    return jsonify(result)

@app.route('/api/shop/buy/<int:item_id>', methods=['POST'])
@login_required
@limiter.limit("10 per minute")
@api_logged
def buy_shop_item(item_id):
    user = User.query.get(session['user_id'])
    item = ShopItem.query.get_or_404(item_id)
    
    if not item.is_active:
        return jsonify({'success': False, 'message': 'Товар недоступен'}), 400
    
    if item.stock == 0:
        return jsonify({'success': False, 'message': 'Товар закончился'}), 400
    
    # Проверяем баланс
    balance = user.currency.balance if user.currency else 0
    if balance < item.price:
        return jsonify({'success': False, 'message': 'Недостаточно средств'}), 400
    
    # Проверяем, не куплен ли уже товар
    existing = UserInventory.query.filter_by(user_id=user.id, item_id=item_id).first()
    if existing:
        return jsonify({'success': False, 'message': 'Товар уже куплен'}), 400
    
    # Совершаем покупку
    if user.currency:
        user.currency.balance -= item.price
        user.currency.total_spent += item.price
    
    # Обновляем статистику товара
    item.sales_count += 1
    if item.stock > 0:
        item.stock -= 1
    
    # Создаем транзакцию
    transaction = CurrencyTransaction(
        user_id=user.id,
        amount=-item.price,
        reason=f'purchase_{item.type}',
        transaction_metadata=json.dumps({'item_id': item.id, 'item_name': item.name})
    )
    db.session.add(transaction)
    
    # Добавляем в инвентарь
    inventory = UserInventory(user_id=user.id, item_id=item_id)
    db.session.add(inventory)
    
    # Обновляем статистику пользователя
    stats = UserStatistic.query.filter_by(user_id=user.id).first()
    if stats:
        stats.items_purchased += 1
    
    db.session.commit()
    
    # Инвалидируем кэш
    invalidate_cache(f'shop_items*')
    
    # Отправляем уведомление в Telegram
    if user.telegram_id:
        try:
            send_telegram_message(
                user.telegram_id,
                f"🛍️ *Покупка совершена!*\n\n"
                f"Товар: {item.name}\n"
                f"Цена: {item.price} монет\n"
                f"Новый баланс: {user.currency.balance} монет\n\n"
                f"Товар добавлен в твой инвентарь!"
            )
        except Exception as e:
            logger.error(f"Failed to send Telegram notification: {e}")
    
    return jsonify({
        'success': True,
        'message': 'Покупка совершена успешно',
        'balance': user.currency.balance,
        'item': {
            'id': item.id,
            'name': item.name,
            'type': item.type
        }
    })

# Инвентарь
@app.route('/api/inventory')
@login_required
@api_logged
def get_inventory():
    user = User.query.get(session['user_id'])
    
    inventory = UserInventory.query.filter_by(user_id=user.id).join(ShopItem).order_by(UserInventory.purchased_at.desc()).all()
    
    result = []
    for inv in inventory:
        result.append({
            'id': inv.item.id,
            'name': inv.item.name,
            'type': inv.item.type,
            'category': inv.item.category.name if inv.item.category else '',
            'data': inv.item.get_data_dict(),
            'equipped': inv.equipped,
            'purchased_at': inv.purchased_at.isoformat() if inv.purchased_at else None,
            'rarity': inv.item.rarity
        })
    
    return jsonify(result)

@app.route('/api/inventory/equip/<int:item_id>', methods=['POST'])
@login_required
@api_logged
def equip_item(item_id):
    user = User.query.get(session['user_id'])
    
    # Проверяем, есть ли предмет в инвентаре
    inventory_item = UserInventory.query.filter_by(user_id=user.id, item_id=item_id).first()
    if not inventory_item:
        return jsonify({'success': False, 'message': 'Предмет не найден в инвентаре'}), 404
    
    item = inventory_item.item
    
    # Снимаем все предметы того же типа
    same_type_items = UserInventory.query.filter_by(user_id=user.id).join(ShopItem).filter(ShopItem.type == item.type).all()
    for inv_item in same_type_items:
        inv_item.equipped = False
    
    # Одеваем выбранный предмет
    inventory_item.equipped = True
    
    db.session.commit()
    
    return jsonify({'success': True, 'message': f'Предмет "{item.name}" применен'})

# Валютная система
@app.route('/api/currency/balance')
@login_required
@api_logged
def get_currency_balance():
    user = User.query.get(session['user_id'])
    balance = user.currency.balance if user.currency else 0
    
    return jsonify({
        'balance': balance,
        'total_earned': user.currency.total_earned if user.currency else 0,
        'total_spent': user.currency.total_spent if user.currency else 0
    })

# Музыкальные сервисы
@app.route('/api/music/check_yandex')
@login_required
@api_logged
def check_yandex_token():
    user = User.query.get(session['user_id'])
    
    if not user.yandex_token:
        return jsonify({'valid': False, 'message': 'Токен не настроен'})
    
    try:
        client = get_yandex_client(user.id)
        if not client:
            return jsonify({'valid': False, 'message': 'Ошибка подключения'})
        
        account = client.account_status()
        return jsonify({
            'valid': True,
            'account': {
                'login': account.account.login,
                'premium': getattr(account.account, 'premium', False)
            }
        })
    except Exception as e:
        return jsonify({'valid': False, 'message': f'Ошибка: {str(e)}'})

@app.route('/api/music/save_token', methods=['POST'])
@login_required
@api_logged
def save_token():
    user = User.query.get(session['user_id'])
    data = request.get_json()
    
    token = data.get('token', '').strip()
    service = data.get('service', 'yandex')
    
    if not token:
        return jsonify({'success': False, 'message': 'Токен не может быть пустым'})
    
    try:
        if service == 'yandex':
            # Проверяем токен
            client = get_yandex_client_cached(token)
            if not client:
                return jsonify({'success': False, 'message': 'Неверный токен Яндекс.Музыки'})
            
            user.yandex_token = token
            
        elif service == 'vk':
            # Проверяем токен VK
            vk_client = get_vk_client_cached(token)
            if not vk_client:
                return jsonify({'success': False, 'message': 'Неверный токен VK'})
            
            user.vk_token = token
        
        else:
            return jsonify({'success': False, 'message': 'Неизвестный сервис'})
        
        db.session.commit()
        
        # Очищаем кэш рекомендаций
        cache.delete_memoized(get_recommendations)
        
        return jsonify({'success': True, 'message': 'Токен успешно сохранен'})
    
    except Exception as e:
        return jsonify({'success': False, 'message': f'Ошибка: {str(e)}'})

# Рекомендации
@app.route('/api/recommendations')
@login_required
@cache.cached(timeout=300, key_prefix=lambda: f'recommendations_{session["user_id"]}')
@api_logged
def get_recommendations():
    user = User.query.get(session['user_id'])
    service = user.settings.music_service if user.settings else 'yandex'
    
    recommendations = recommender.get_enhanced_recommendations(user.id, service)
    return jsonify(recommendations)

# Плейлисты
@app.route('/api/playlists')
@login_required
@cache_response(timeout=180)
@api_logged
def get_playlists():
    user = User.query.get(session['user_id'])
    service = user.settings.music_service if user.settings else 'yandex'
    
    result = []
    
    if service == 'yandex':
        client = get_yandex_client(user.id)
        if not client:
            return jsonify({'error': 'Токен Яндекс.Музыки не настроен'}), 400
        
        try:
            playlists = client.users_playlists_list()
            for playlist in playlists:
                if hasattr(playlist, 'collective') and playlist.collective:
                    continue
                
                cover_uri = None
                if hasattr(playlist, 'cover') and playlist.cover:
                    if hasattr(playlist.cover, 'uri') and playlist.cover.uri:
                        cover_uri = f"https://{playlist.cover.uri.replace('%%', '400x400')}"
                
                result.append({
                    'id': f"yandex_{playlist.kind}",
                    'title': playlist.title,
                    'track_count': playlist.track_count,
                    'cover_uri': cover_uri,
                    'service': 'yandex'
                })
        except Exception as e:
            logger.error(f"Yandex playlists error: {e}")
    
    elif service == 'vk':
        vk_client = get_vk_client(user.id)
        if not vk_client:
            return jsonify({'error': 'Токен VK не настроен'}), 400
        
        try:
            playlists = vk_client.audio.getPlaylists()
            if 'items' in playlists:
                for playlist in playlists['items']:
                    result.append({
                        'id': f"vk_{playlist['id']}",
                        'title': playlist['title'],
                        'track_count': playlist['count'],
                        'cover_uri': playlist.get('photo', {}).get('photo_300'),
                        'service': 'vk'
                    })
        except Exception as e:
            logger.error(f"VK playlists error: {e}")
    
    return jsonify(result)

# Воспроизведение трека
@app.route('/api/play/<service>_<track_id>')
@login_required
@limiter.limit("30 per minute")
@api_logged
def play_track(service, track_id):
    user = User.query.get(session['user_id'])
    
    if service == 'yandex':
        client = get_yandex_client(user.id)
        if not client:
            return jsonify({'error': 'Токен Яндекс.Музыки не настроен'}), 400
        
        try:
            track = client.tracks(track_id)[0]
            download_info = track.get_download_info()
            
            if not download_info:
                return jsonify({'error': 'Не удалось получить информацию для воспроизведения'}), 404
            
            # Выбираем лучшее качество
            best_quality = max(download_info, key=lambda x: x.bitrate_in_kbps)
            download_url = best_quality.get_direct_link()
            
            # Сохраняем в историю
            history = ListeningHistory(
                user_id=user.id,
                track_id=f"yandex_{track_id}",
                track_data=json.dumps({
                    'title': track.title,
                    'artists': [artist.name for artist in track.artists],
                    'duration': track.duration_ms,
                    'service': 'yandex'
                }),
                service='yandex'
            )
            db.session.add(history)
            
            # Обновляем статистику
            stats = UserStatistic.query.filter_by(user_id=user.id).first()
            if stats:
                stats.tracks_listened += 1
                stats.minutes_listened += track.duration_ms // 60000
            
            # Начисляем валюту
            add_currency(user.id, 1, 'listen_track', {'track_id': track_id, 'service': 'yandex'})
            
            db.session.commit()
            
            return jsonify({
                'url': download_url,
                'title': track.title,
                'artists': [artist.name for artist in track.artists],
                'duration': track.duration_ms,
                'cover_uri': f"https://{track.cover_uri.replace('%%', '300x300')}" if track.cover_uri else None
            })
        except Exception as e:
            logger.error(f"Play track error: {e}")
            return jsonify({'error': str(e)}), 500
    
    elif service == 'vk':
        vk_client = get_vk_client(user.id)
        if not vk_client:
            return jsonify({'error': 'Токен VK не настроен'}), 400
        
        try:
            track_info = vk_client.audio.getById(audios=track_id)
            if not track_info or 'url' not in track_info[0]:
                return jsonify({'error': 'Трек не найден'}), 404
            
            track = track_info[0]
            
            # Сохраняем в историю
            history = ListeningHistory(
                user_id=user.id,
                track_id=f"vk_{track_id}",
                track_data=json.dumps({
                    'title': track['title'],
                    'artists': [track['artist']],
                    'duration': track['duration'] * 1000,
                    'service': 'vk'
                }),
                service='vk'
            )
            db.session.add(history)
            
            # Обновляем статистику
            stats = UserStatistic.query.filter_by(user_id=user.id).first()
            if stats:
                stats.tracks_listened += 1
                stats.minutes_listened += track['duration'] // 60
            
            # Начисляем валюту
            add_currency(user.id, 1, 'listen_track', {'track_id': track_id, 'service': 'vk'})
            
            db.session.commit()
            
            return jsonify({
                'url': track['url'],
                'title': track['title'],
                'artists': [track['artist']],
                'duration': track['duration'] * 1000,
                'cover_uri': track.get('album', {}).get('thumb', {}).get('photo_300')
            })
        except Exception as e:
            logger.error(f"VK play track error: {e}")
            return jsonify({'error': str(e)}), 500
    
    return jsonify({'error': 'Неизвестный сервис'}), 400

# Ежедневная награда
@app.route('/api/daily_reward', methods=['POST'])
@login_required
@limiter.limit("1 per day")
@api_logged
def daily_reward():
    user = User.query.get(session['user_id'])
    
    # Проверяем, получал ли пользователь награду сегодня
    last_reward = CurrencyTransaction.query.filter_by(
        user_id=user.id,
        reason='daily_reward'
    ).order_by(CurrencyTransaction.created_at.desc()).first()
    
    if last_reward and last_reward.created_at.date() == datetime.utcnow().date():
        return jsonify({'success': False, 'message': 'Вы уже получали награду сегодня'})
    
    # Размер награды зависит от количества дней подряд
    stats = UserStatistic.query.filter_by(user_id=user.id).first()
    if not stats:
        stats = UserStatistic(user_id=user.id)
        db.session.add(stats)
    
    # Вычисляем количество дней подряд
    consecutive_days = 1
    if stats.last_daily_reward:
        days_diff = (datetime.utcnow().date() - stats.last_daily_reward.date()).days
        if days_diff == 1:
            # Вчера получал - увеличиваем серию
            consecutive_days = min(stats.daily_rewards_claimed % 7 + 1, 7)
    
    # Награда: базовая + бонус за серию
    base_reward = random.randint(10, 25)
    bonus = consecutive_days * 5
    total_reward = base_reward + bonus
    
    # Выдаем награду
    if add_currency(user.id, total_reward, 'daily_reward', {'consecutive_days': consecutive_days}):
        stats.last_daily_reward = datetime.utcnow()
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': f'Получено {total_reward} монет! (Серия: {consecutive_days} дней)',
            'reward': total_reward,
            'consecutive_days': consecutive_days
        })
    else:
        return jsonify({'success': False, 'message': 'Ошибка выдачи награды'})

# Настройки
@app.route('/api/settings', methods=['GET', 'PUT'])
@login_required
@api_logged
def user_settings():
    user = User.query.get(session['user_id'])
    
    if request.method == 'GET':
        if not user.settings:
            user.settings = UserSettings(user_id=user.id)
            db.session.commit()
        
        return jsonify({
            'theme': user.settings.theme,
            'language': user.settings.language,
            'auto_play': user.settings.auto_play,
            'show_explicit': user.settings.show_explicit,
            'music_service': user.settings.music_service,
            'notifications_enabled': user.settings.notifications_enabled,
            'privacy_level': user.settings.privacy_level
        })
    
    elif request.method == 'PUT':
        data = request.get_json()
        
        if not user.settings:
            user.settings = UserSettings(user_id=user.id)
        
        if 'theme' in data:
            user.settings.theme = data['theme']
        
        if 'language' in data:
            user.settings.language = data['language']
        
        if 'auto_play' in data:
            user.settings.auto_play = bool(data['auto_play'])
        
        if 'show_explicit' in data:
            user.settings.show_explicit = bool(data['show_explicit'])
        
        if 'music_service' in data:
            user.settings.music_service = data['music_service']
        
        if 'notifications_enabled' in data:
            user.settings.notifications_enabled = bool(data['notifications_enabled'])
        
        if 'privacy_level' in data:
            user.settings.privacy_level = data['privacy_level']
        
        db.session.commit()
        
        return jsonify({'success': True, 'message': 'Настройки сохранены'})

# Друзья
@app.route('/api/friends')
@login_required
@api_logged
def get_friends():
    user = User.query.get(session['user_id'])
    
    friends = Friend.query.filter(
        (Friend.user_id == user.id) | (Friend.friend_id == user.id),
        Friend.status == 'accepted'
    ).all()
    
    result = []
    for friend_rel in friends:
        friend_user = User.query.get(friend_rel.friend_id if friend_rel.user_id == user.id else friend_rel.user_id)
        if friend_user:
            result.append({
                'id': friend_user.id,
                'username': friend_user.username,
                'display_name': friend_user.display_name,
                'avatar_url': friend_user.avatar_url,
                'taste_match': friend_rel.taste_match,
                'friends_since': friend_rel.created_at.isoformat() if friend_rel.created_at else None
            })
    
    return jsonify(result)

# --- Админ маршруты ---
@app.route('/admin')
@login_required
@admin_required
def admin_panel():
    return render_template('admin.html')

@app.route('/api/admin/stats')
@login_required
@admin_required
@api_logged
def admin_stats():
    # Основная статистика
    total_users = User.query.count()
    active_users = User.query.filter(User.last_active >= datetime.utcnow() - timedelta(days=1)).count()
    total_items = ShopItem.query.count()
    total_sales = db.session.query(db.func.sum(ShopItem.sales_count)).scalar() or 0
    total_currency = db.session.query(db.func.sum(UserCurrency.balance)).scalar() or 0
    
    # Статистика API
    api_stats = get_api_stats('day')
    
    # Telegram статистика
    telegram_users = User.query.filter(User.telegram_id.isnot(None)).count()
    
    return jsonify({
        'users': {
            'total': total_users,
            'active_today': active_users,
            'new_today': User.query.filter(User.created_at >= datetime.utcnow().date()).count(),
            'telegram_linked': telegram_users
        },
        'shop': {
            'total_items': total_items,
            'total_sales': total_sales,
            'revenue': total_sales * 10
        },
        'currency': {
            'total_in_circulation': total_currency,
            'transactions_today': CurrencyTransaction.query.filter(
                CurrencyTransaction.created_at >= datetime.utcnow().date()
            ).count()
        },
        'api': {
            'requests_today': len(api_stats),
            'endpoints': api_stats
        }
    })

@app.route('/api/admin/users')
@login_required
@admin_required
@api_logged
def admin_users():
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 50, type=int)
    
    users = User.query.order_by(User.created_at.desc())\
        .paginate(page=page, per_page=per_page, error_out=False)
    
    result = []
    for user in users.items:
        result.append({
            'id': user.id,
            'username': user.username,
            'email': user.email,
            'display_name': user.display_name,
            'is_admin': user.is_admin,
            'telegram_linked': bool(user.telegram_id),
            'created_at': user.created_at.isoformat() if user.created_at else None,
            'last_active': user.last_active.isoformat() if user.last_active else None,
            'balance': user.currency.balance if user.currency else 0
        })
    
    return jsonify({
        'users': result,
        'total': users.total,
        'pages': users.pages,
        'current_page': users.page
    })

@app.route('/api/admin/add_currency', methods=['POST'])
@login_required
@admin_required
@api_logged
def admin_add_currency():
    data = request.get_json()
    
    user_id = data.get('user_id')
    amount = data.get('amount', 0)
    reason = data.get('reason', 'admin_grant')
    
    if not user_id or amount == 0:
        return jsonify({'success': False, 'message': 'Неверные параметры'}), 400
    
    user = User.query.get(user_id)
    if not user:
        return jsonify({'success': False, 'message': 'Пользователь не найден'}), 404
    
    if add_currency(user.id, amount, reason, {'admin_action': True}):
        return jsonify({'success': True, 'message': f'Добавлено {amount} валюты пользователю {user.username}'})
    else:
        return jsonify({'success': False, 'message': 'Ошибка добавления валюты'})

# Управление магазином
@app.route('/api/admin/shop/items', methods=['GET', 'POST'])
@login_required
@admin_required
@api_logged
def admin_shop_items():
    if request.method == 'GET':
        # Получаем все товары
        items = ShopItem.query.all()
        result = []
        
        for item in items:
            result.append({
                'id': item.id,
                'name': item.name,
                'type': item.type,
                'category_id': item.category_id,
                'category_name': item.category.name if item.category else '',
                'price': item.price,
                'data': json.loads(item.data) if item.data else {},
                'rarity': item.rarity,
                'stock': item.stock,
                'sales_count': item.sales_count,
                'is_active': item.is_active,
                'created_at': item.created_at.isoformat() if item.created_at else None
            })
        
        return jsonify(result)
    
    elif request.method == 'POST':
        # Создание нового товара
        data = request.get_json()
        
        # Проверяем обязательные поля
        required_fields = ['name', 'type', 'category_id', 'price']
        for field in required_fields:
            if field not in data:
                return jsonify({'success': False, 'message': f'Отсутствует поле: {field}'}), 400
        
        # Создаем товар
        item = ShopItem(
            name=data['name'],
            type=data['type'],
            category_id=data['category_id'],
            price=data['price'],
            data=json.dumps(data.get('data', {})),
            rarity=data.get('rarity', 'common'),
            stock=data.get('stock', -1),
            is_active=data.get('is_active', True)
        )
        
        db.session.add(item)
        db.session.commit()
        
        # Инвалидируем кэш
        invalidate_cache('shop_items*')
        
        return jsonify({
            'success': True,
            'message': 'Товар создан',
            'item_id': item.id
        })

@app.route('/api/admin/shop/items/<int:item_id>', methods=['PUT', 'DELETE'])
@login_required
@admin_required
@api_logged
def admin_shop_item(item_id):
    item = ShopItem.query.get_or_404(item_id)
    
    if request.method == 'PUT':
        data = request.get_json()
        
        # Обновляем поля
        if 'name' in data:
            item.name = data['name']
        if 'type' in data:
            item.type = data['type']
        if 'category_id' in data:
            item.category_id = data['category_id']
        if 'price' in data:
            item.price = data['price']
        if 'data' in data:
            item.data = json.dumps(data['data'])
        if 'rarity' in data:
            item.rarity = data['rarity']
        if 'stock' in data:
            item.stock = data['stock']
        if 'is_active' in data:
            item.is_active = data['is_active']
        
        db.session.commit()
        
        # Инвалидируем кэш
        invalidate_cache('shop_items*')
        
        return jsonify({'success': True, 'message': 'Товар обновлен'})
    
    elif request.method == 'DELETE':
        # Проверяем, не куплен ли товар
        if UserInventory.query.filter_by(item_id=item_id).count() > 0:
            return jsonify({'success': False, 'message': 'Невозможно удалить товар, который уже куплен'}), 400
        
        db.session.delete(item)
        db.session.commit()
        
        # Инвалидируем кэш
        invalidate_cache('shop_items*')
        
        return jsonify({'success': True, 'message': 'Товар удален'})

@app.route('/api/admin/shop/categories', methods=['GET', 'POST'])
@login_required
@admin_required
@api_logged
def admin_shop_categories():
    if request.method == 'GET':
        categories = ShopCategory.query.all()
        result = []
        
        for cat in categories:
            result.append({
                'id': cat.id,
                'name': cat.name,
                'description': cat.description,
                'icon': cat.icon,
                'display_order': cat.display_order,
                'is_active': cat.is_active,
                'item_count': cat.items.count()
            })
        
        return jsonify(result)
    
    elif request.method == 'POST':
        data = request.get_json()
        
        if 'name' not in data:
            return jsonify({'success': False, 'message': 'Отсутствует название категории'}), 400
        
        category = ShopCategory(
            name=data['name'],
            description=data.get('description', ''),
            icon=data.get('icon', 'fas fa-question'),
            display_order=data.get('display_order', 0),
            is_active=data.get('is_active', True)
        )
        
        db.session.add(category)
        db.session.commit()
        
        # Инвалидируем кэш
        invalidate_cache('shop_categories*')
        
        return jsonify({
            'success': True,
            'message': 'Категория создана',
            'category_id': category.id
        })

@app.route('/api/admin/shop/categories/<int:category_id>', methods=['PUT', 'DELETE'])
@login_required
@admin_required
@api_logged
def admin_shop_category(category_id):
    category = ShopCategory.query.get_or_404(category_id)
    
    if request.method == 'PUT':
        data = request.get_json()
        
        if 'name' in data:
            category.name = data['name']
        if 'description' in data:
            category.description = data['description']
        if 'icon' in data:
            category.icon = data['icon']
        if 'display_order' in data:
            category.display_order = data['display_order']
        if 'is_active' in data:
            category.is_active = data['is_active']
        
        db.session.commit()
        
        # Инвалидируем кэш
        invalidate_cache('shop_categories*')
        
        return jsonify({'success': True, 'message': 'Категория обновлена'})
    
    elif request.method == 'DELETE':
        # Проверяем, нет ли товаров в категории
        if category.items.count() > 0:
            return jsonify({'success': False, 'message': 'Невозможно удалить категорию с товарами'}), 400
        
        db.session.delete(category)
        db.session.commit()
        
        # Инвалидируем кэш
        invalidate_cache('shop_categories*')
        
        return jsonify({'success': True, 'message': 'Категория удалена'})

# Управление баннерами
@app.route('/api/admin/banners', methods=['GET', 'POST'])
@login_required
@admin_required
@api_logged
def admin_banners():
    if request.method == 'GET':
        banners = ShopBanner.query.all()
        result = []
        
        for banner in banners:
            result.append({
                'id': banner.id,
                'name': banner.name,
                'image_url': banner.image_url,
                'preview_url': banner.preview_url,
                'price': banner.price,
                'rarity': banner.rarity,
                'is_active': banner.is_active,
                'created_at': banner.created_at.isoformat() if banner.created_at else None
            })
        
        return jsonify(result)
    
    elif request.method == 'POST':
        data = request.get_json()
        
        if not data.get('name') or not data.get('image_url'):
            return jsonify({'success': False, 'message': 'Название и URL изображения обязательны'}), 400
        
        banner = ShopBanner(
            name=data['name'],
            image_url=data['image_url'],
            preview_url=data.get('preview_url', data['image_url']),
            price=data.get('price', 0),
            rarity=data.get('rarity', 'common'),
            is_active=data.get('is_active', True)
        )
        
        db.session.add(banner)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Баннер создан',
            'banner_id': banner.id
        })

@app.route('/api/admin/banners/<int:banner_id>', methods=['PUT', 'DELETE'])
@login_required
@admin_required
@api_logged
def admin_banner(banner_id):
    banner = ShopBanner.query.get_or_404(banner_id)
    
    if request.method == 'PUT':
        data = request.get_json()
        
        if 'name' in data:
            banner.name = data['name']
        if 'image_url' in data:
            banner.image_url = data['image_url']
        if 'preview_url' in data:
            banner.preview_url = data['preview_url']
        if 'price' in data:
            banner.price = data['price']
        if 'rarity' in data:
            banner.rarity = data['rarity']
        if 'is_active' in data:
            banner.is_active = data['is_active']
        
        db.session.commit()
        
        return jsonify({'success': True, 'message': 'Баннер обновлен'})
    
    elif request.method == 'DELETE':
        db.session.delete(banner)
        db.session.commit()
        
        return jsonify({'success': True, 'message': 'Баннер удален'})

# Загрузка файлов
@app.route('/api/admin/upload', methods=['POST'])
@login_required
@admin_required
@api_logged
def admin_upload():
    if 'file' not in request.files:
        return jsonify({'success': False, 'message': 'Нет файла'}), 400
    
    file = request.files['file']
    file_type = request.form.get('type', 'shop_item')
    
    if file.filename == '':
        return jsonify({'success': False, 'message': 'Файл не выбран'}), 400
    
    # Проверяем расширение файла
    allowed_extensions = {'png', 'jpg', 'jpeg', 'gif', 'webp', 'svg'}
    if '.' in file.filename:
        ext = file.filename.rsplit('.', 1)[1].lower()
        if ext not in allowed_extensions:
            return jsonify({'success': False, 'message': 'Недопустимый формат файла'}), 400
    
    # Сохраняем файл
    try:
        file_data = file.read()
        
        # Валидация изображения
        if file_type in ['avatar', 'banner', 'shop_item']:
            valid, message = validate_image(file_data)
            if not valid:
                return jsonify({'success': False, 'message': message}), 400
        
        saved_path = save_uploaded_file(file_data, file_type)
        
        if saved_path:
            return jsonify({
                'success': True,
                'message': 'Файл загружен',
                'url': saved_path
            })
        else:
            return jsonify({'success': False, 'message': 'Ошибка сохранения файла'}), 500
            
    except Exception as e:
        logger.error(f"File upload error: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500

# Управление Telegram ботом
@app.route('/api/admin/bot/status')
@login_required
@admin_required
@api_logged
def admin_bot_status():
    """Статус Telegram бота"""
    bot_status = {
        'running': telegram_bot is not None and hasattr(telegram_bot, 'bot_app') and telegram_bot.bot_app is not None,
        'token_set': bool(os.getenv('TELEGRAM_BOT_TOKEN')),
        'auto_start': os.getenv('RUN_TELEGRAM_BOT', 'true').lower() == 'true',
        'server_url': os.getenv('SERVER_URL', 'http://localhost:5001')
    }
    
    return jsonify(bot_status)

@app.route('/api/admin/bot/restart', methods=['POST'])
@login_required
@admin_required
@api_logged
def admin_bot_restart():
    """Перезапуск Telegram бота"""
    global telegram_bot
    
    # Останавливаем текущий бот
    if telegram_bot:
        try:
            stop_telegram_bot()
        except Exception as e:
            logger.error(f"Error stopping bot: {e}")
    
    # Запускаем заново
    telegram_token = os.getenv('TELEGRAM_BOT_TOKEN')
    if telegram_token:
        try:
            init_telegram_bot(telegram_token)
            return jsonify({'success': True, 'message': 'Бот перезапущен'})
        except Exception as e:
            return jsonify({'success': False, 'message': f'Ошибка: {str(e)}'}), 500
    else:
        return jsonify({'success': False, 'message': 'Токен бота не настроен'}), 400

@app.route('/api/admin/bot/test_message', methods=['POST'])
@login_required
@admin_required
@api_logged
def admin_bot_test_message():
    """Тестовая отправка сообщения через бота"""
    data = request.get_json()
    
    telegram_id = data.get('telegram_id')
    message = data.get('message', 'Тестовое сообщение от админ-панели')
    
    if not telegram_id:
        return jsonify({'success': False, 'message': 'Не указан telegram_id'}), 400
    
    try:
        success = send_telegram_message(telegram_id, message)
        if success:
            return jsonify({'success': True, 'message': 'Сообщение отправлено'})
        else:
            return jsonify({'success': False, 'message': 'Не удалось отправить сообщение'})
    except Exception as e:
        return jsonify({'success': False, 'message': f'Ошибка: {str(e)}'})

# Статические файлы
@app.route('/static/<path:filename>')
def static_files(filename):
    return send_from_directory('static', filename)

@app.route('/uploads/<path:filename>')
def uploaded_files(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

# Health check
@app.route('/health')
def health_check():
    try:
        # Проверка базы данных
        db.session.execute('SELECT 1')
        
        # Проверка Redis (если есть)
        redis_ok = False
        if redis_client:
            try:
                redis_client.ping()
                redis_ok = True
            except:
                redis_ok = False
        
        return jsonify({
            'status': 'healthy',
            'timestamp': datetime.utcnow().isoformat(),
            'database': 'connected',
            'redis': 'connected' if redis_ok else 'disconnected',
            'telegram_bot': 'active' if telegram_bot and hasattr(telegram_bot, 'bot_app') else 'disabled',
            'version': '2.0.0'
        }), 200
    except Exception as e:
        return jsonify({
            'status': 'unhealthy',
            'error': str(e)
        }), 500

# Обработчики ошибок
@app.errorhandler(404)
def not_found(error):
    return jsonify({'error': 'Not found'}), 404

@app.errorhandler(500)
def internal_error(error):
    logger.error(f"Server Error: {error}")
    return jsonify({'error': 'Internal server error'}), 500

@app.errorhandler(429)
def ratelimit_handler(e):
    return jsonify({'error': 'Rate limit exceeded'}), 429

# Запуск приложения
if __name__ == '__main__':
    port = int(os.getenv('PORT', 5001))
    debug = os.getenv('FLASK_ENV') == 'development'
    
    # Запускаем сервер
    app.run(host='0.0.0.0', port=port, debug=debug, threaded=True)