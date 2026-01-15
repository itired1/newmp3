from flask import Flask, render_template, jsonify, request, session, redirect, url_for, send_from_directory
from flask_migrate import Migrate
from flask_caching import Cache
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_cors import CORS
from models import db, User, UserCurrency, ShopCategory, ShopItem, UserInventory, TelegramSession
from models import CurrencyTransaction, UserSettings, UserActivity, Friend, ListeningHistory, UserTheme
from models import CacheItem, UserStatistic, APILog
from utils import login_required, admin_required, add_currency, recommender, cache_response
from utils import send_verification_email, save_uploaded_file, get_yandex_client, get_vk_client
from utils import log_api_request, get_api_stats, cache_db_set, cache_db_get, clean_expired_cache
from utils import get_yandex_client_cached, get_vk_client_cached, redis_client
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

# Импортируем Telegram бота
from telegram_bot import init_telegram_bot, telegram_bot

# Определяем базовую директорию
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Создаем папки для логов и загрузок перед настройкой логирования
logs_dir = os.path.join(BASE_DIR, 'logs')
avatars_dir = os.path.join(BASE_DIR, 'static', 'uploads', 'avatars')
banners_dir = os.path.join(BASE_DIR, 'static', 'uploads', 'banners')

os.makedirs(logs_dir, exist_ok=True)
os.makedirs(avatars_dir, exist_ok=True)
os.makedirs(banners_dir, exist_ok=True)

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
                
                # Инициализируем Telegram бота
                telegram_token = os.getenv('TELEGRAM_BOT_TOKEN')
                if telegram_token:
                    init_telegram_bot(telegram_token)
                    logger.info("Telegram bot initialized")
                
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
            ('animations', 'Анимации', 'fas fa-film', 6)
        ]
        
        for cat_name, cat_desc, cat_icon, order in categories:
            category = ShopCategory.query.filter_by(name=cat_name).first()
            if not category:
                category = ShopCategory(
                    name=cat_name,
                    description=cat_desc,
                    icon=cat_icon,
                    display_order=order
                )
                db.session.add(category)
        
        db.session.commit()
        
        # Создаем товары
        shop_items = [
            ('Темная тема Premium', 'theme', 'themes', 50, 
             '{"styles": {"--bg-primary": "#0a0a0a", "--bg-secondary": "#141414", "--accent": "#ff6b6b", "--text-primary": "#ffffff"}}', 'rare'),
            
            ('Синяя тема Ocean', 'theme', 'themes', 40,
             '{"styles": {"--bg-primary": "#0a1929", "--bg-secondary": "#132f4c", "--accent": "#1976d2", "--text-primary": "#e3f2fd"}}', 'common'),
            
            ('Аватар "Звезда"', 'avatar', 'avatars', 20,
             '{"image_url": "/static/shop/avatars/star.png", "unlockable": true}', 'common'),
            
            ('Аватар "Лунный свет"', 'avatar', 'avatars', 25,
             '{"image_url": "/static/shop/avatars/moon.png", "unlockable": true}', 'common'),
            
            ('Баннер "Горизонт"', 'profile_banner', 'banners', 45,
             '{"image_url": "/static/shop/banners/horizon.jpg", "preview": "/static/shop/banners/horizon.jpg"}', 'rare'),
            
            ('Баннер "Градиент"', 'profile_banner', 'banners', 35,
             '{"image_url": "/static/shop/banners/gradient.jpg", "preview": "/static/shop/banners/gradient.jpg"}', 'common'),
            
            ('Баннер "Космос"', 'profile_banner', 'banners', 55,
             '{"image_url": "/static/shop/banners/space.jpg", "preview": "/static/shop/banners/space.jpg"}', 'epic'),
            
            ('Баннер "Огненный дракон"', 'profile_banner', 'banners', 100,
             '{"image_url": "/static/shop/banners/dragon.gif", "preview": "/static/shop/banners/dragon.gif", "animation": "gif"}', 'legendary'),
            
            ('Баннер "Космическое сияние"', 'profile_banner', 'banners', 100,
             '{"image_url": "/static/shop/banners/cosmic.gif", "preview": "/static/shop/banners/cosmic.gif", "animation": "gif"}', 'legendary'),
            
            ('Бейдж "Меломан"', 'badge', 'badges', 15,
             '{"text": "🎵 Меломан", "color": "#ff6b6b", "animation": "pulse"}', 'common'),
            
            ('Бейдж "VIP"', 'badge', 'badges', 30,
             '{"text": "⭐ VIP", "color": "#ffd700", "animation": "glow"}', 'rare'),
            
            ('Эффект "Неоновое сияние"', 'effect', 'effects', 75,
             '{"css": ".player { filter: drop-shadow(0 0 10px #ff00ff); }", "duration": 30000}', 'epic'),
            
            ('Анимация "Вращение"', 'animation', 'animations', 45,
             '{"css": "@keyframes spin { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }", "element": ".album-cover"}', 'rare')
        ]
        
        for name, item_type, category_name, price, data, rarity in shop_items:
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
                        rarity=rarity
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
            currency = UserCurrency(user_id=admin_user.id, balance=1000)
            db.session.add(currency)
            
            db.session.commit()
            logger.info("Администратор создан: admin / admin123")
    except Exception as e:
        logger.error(f"Ошибка создания администратора: {e}")

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
            # Проверяем, привязан ли Telegram (теперь опционально)
            if not user.telegram_verified:
                logger.info(f"User {user.username} logged in without Telegram verification")
            
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
        
        # Старая регистрация (оставляем для обратной совместимости)
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
        
        # Создаем пользователя (без верификации)
        user = User(
            username=username,
            email=email,
            display_name=username,
            email_verified=True  # Теперь сразу верифицируем
        )
        user.set_password(password)
        
        db.session.add(user)
        db.session.commit()
        
        # Создаем настройки по умолчанию
        settings = UserSettings(user_id=user.id)
        db.session.add(settings)
        
        # Создаем начальную валюту
        currency = UserCurrency(user_id=user.id, balance=50)
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
    # Проверка кода Telegram
    telegram_session = TelegramSession.query.filter_by(
        session_data=json.dumps({'verification_code': telegram_code})
    ).first()
    
    if not telegram_session:
        # Попробуем найти по части JSON
        sessions = TelegramSession.query.all()
        for session in sessions:
            try:
                if session.session_data:
                    data = json.loads(session.session_data)
                    if data.get('verification_code') == telegram_code:
                        telegram_session = session
                        break
            except:
                continue
    
    if not telegram_session:
        return render_template('auth.html', mode='register', error='Неверный код Telegram')
    
    # Проверка срока действия кода
    if telegram_session.last_active and \
       telegram_session.last_active < datetime.utcnow() - timedelta(minutes=10):
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
    
    # Получаем данные из сессии
    session_data = json.loads(telegram_session.session_data) if telegram_session.session_data else {}
    
    # Создаем пользователя с привязкой к Telegram
    user = User(
        username=username,
        email=email,
        display_name=username,
        email_verified=True,
        telegram_id=telegram_session.telegram_id,
        telegram_username=telegram_session.username,
        telegram_verified=True
    )
    user.set_password(password)
    
    db.session.add(user)
    
    # Привязываем сессию к пользователю
    telegram_session.user_id = user.id
    telegram_session.session_data = None  # Очищаем код
    
    # Создаем настройки по умолчанию
    settings = UserSettings(user_id=user.id)
    db.session.add(settings)
    
    # Создаем начальную валюту (больше монет за регистрацию через Telegram)
    currency = UserCurrency(user_id=user.id, balance=100)
    db.session.add(currency)
    
    # Создаем статистику
    stats = UserStatistic(user_id=user.id)
    db.session.add(stats)
    
    db.session.commit()
    
    # Отправляем уведомление в Telegram
    if telegram_bot:
        try:
            # Используем асинхронный вызов в отдельном потоке
            import asyncio
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            async def send_notification():
                try:
                    await telegram_bot.bot_app.bot.send_message(
                        chat_id=telegram_session.chat_id,
                        text=f"✅ Регистрация успешна!\n\n"
                             f"Добро пожаловать в itired, {username}!\n"
                             f"На твой счет начислено 100 монет 🎉\n\n"
                             f"Используй команды:\n"
                             f"/balance - проверить баланс\n"
                             f"/daily - ежедневная награда\n"
                             f"/profile - профиль",
                        parse_mode="Markdown"
                    )
                except Exception as e:
                    logger.error(f"Failed to send Telegram notification: {e}")
            
            loop.run_until_complete(send_notification())
        except Exception as e:
            logger.error(f"Error sending Telegram notification: {e}")
    
    # Авторизуем пользователя
    session.permanent = True
    session['user_id'] = user.id
    session['username'] = user.username
    
    return redirect(url_for('index'))

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

# --- API маршруты ---

# Профиль пользователя
@app.route('/api/profile')
@login_required
@api_logged
def get_profile_api():
    user = User.query.get(session['user_id'])
    if not user:
        return jsonify({'error': 'Пользователь не найден'}), 404
    
    yandex_profile = None
    vk_profile = None
    
    if user.yandex_token:
        try:
            client = get_yandex_client(user.id)
            if client:
                account = client.account_status()
                yandex_profile = {
                    'username': account.account.login,
                    'premium': getattr(account.account, 'premium', False),
                    'uid': getattr(account.account, 'uid', '')
                }
        except Exception as e:
            logger.warning(f"Yandex profile error: {e}")
    
    if user.vk_token:
        try:
            vk_client = get_vk_client(user.id)
            if vk_client:
                vk_user = vk_client.users.get()[0]
                vk_profile = {
                    'first_name': vk_user['first_name'],
                    'last_name': vk_user['last_name'],
                    'uid': vk_user['id']
                }
        except Exception as e:
            logger.warning(f"VK profile error: {e}")
    
    return jsonify({
        'user': user.to_dict(),
        'yandex': yandex_profile,
        'vk': vk_profile,
        'settings': {
            'theme': user.settings.theme if user.settings else 'dark',
            'music_service': user.settings.music_service if user.settings else 'yandex'
        }
    })

@app.route('/api/profile', methods=['POST'])
@login_required
@api_logged
def update_profile():
    user = User.query.get(session['user_id'])
    if not user:
        return jsonify({'error': 'Пользователь не найден'}), 404
    
    data = request.get_json()
    
    if 'display_name' in data:
        user.display_name = data['display_name'].strip()[:100]
    
    if 'bio' in data:
        user.bio = data['bio'].strip()[:500]
    
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
    
    query = ShopItem.query.filter_by(is_active=True)
    
    if category_id:
        query = query.filter_by(category_id=category_id)
    
    if rarity:
        query = query.filter_by(rarity=rarity)
    
    if min_price is not None:
        query = query.filter(ShopItem.price >= min_price)
    
    if max_price is not None:
        query = query.filter(ShopItem.price <= max_price)
    
    items = query.order_by(ShopItem.price).all()
    user = User.query.get(session['user_id'])
    owned_item_ids = [inv.item_id for inv in user.inventory]
    
    result = []
    for item in items:
        result.append({
            'id': item.id,
            'name': item.name,
            'type': item.type,
            'category': item.category.name,
            'price': item.price,
            'rarity': item.rarity,
            'data': item.get_data_dict(),
            'owned': item.id in owned_item_ids,
            'stock': item.stock,
            'sales_count': item.sales_count
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
    cache.delete_memoized(get_shop_items)
    
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
            'category': inv.item.category.name,
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

@app.route('/api/inventory/unequip/<int:item_id>', methods=['POST'])
@login_required
@api_logged
def unequip_item(item_id):
    user = User.query.get(session['user_id'])
    
    inventory_item = UserInventory.query.filter_by(user_id=user.id, item_id=item_id).first()
    if not inventory_item:
        return jsonify({'success': False, 'message': 'Предмет не найден'}), 404
    
    inventory_item.equipped = False
    db.session.commit()
    
    return jsonify({'success': True, 'message': 'Предмет снят'})

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

@app.route('/api/currency/history')
@login_required
@api_logged
def get_currency_history():
    user = User.query.get(session['user_id'])
    
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    
    transactions = CurrencyTransaction.query.filter_by(user_id=user.id)\
        .order_by(CurrencyTransaction.created_at.desc())\
        .paginate(page=page, per_page=per_page, error_out=False)
    
    result = []
    for transaction in transactions.items:
        result.append({
            'id': transaction.id,
            'amount': transaction.amount,
            'reason': transaction.reason,
            'metadata': json.loads(transaction.transaction_metadata) if transaction.transaction_metadata else None,
            'created_at': transaction.created_at.isoformat() if transaction.created_at else None
        })
    
    return jsonify({
        'transactions': result,
        'total': transactions.total,
        'pages': transactions.pages,
        'current_page': transactions.page
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

@app.route('/api/music/check_vk')
@login_required
@api_logged
def check_vk_token():
    user = User.query.get(session['user_id'])
    
    if not user.vk_token:
        return jsonify({'valid': False, 'message': 'Токен не настроен'})
    
    try:
        vk_client = get_vk_client(user.id)
        if not vk_client:
            return jsonify({'valid': False, 'message': 'Ошибка подключения'})
        
        vk_user = vk_client.users.get()[0]
        return jsonify({
            'valid': True,
            'account': {
                'name': f"{vk_user['first_name']} {vk_user['last_name']}",
                'uid': vk_user['id']
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

@app.route('/api/playlist/<service>_<playlist_id>')
@login_required
@cache_response(timeout=300)
@api_logged
def get_playlist(service, playlist_id):
    user = User.query.get(session['user_id'])
    
    if service == 'yandex':
        client = get_yandex_client(user.id)
        if not client:
            return jsonify({'error': 'Токен Яндекс.Музыки не настроен'}), 400
        
        try:
            playlist = client.users_playlists(int(playlist_id))
            if not playlist:
                return jsonify({'error': 'Плейлист не найден'}), 404
            
            tracks = []
            for track_short in playlist.tracks:
                try:
                    track = track_short.track
                    cover_uri = f"https://{track.cover_uri.replace('%%', '300x300')}" if hasattr(track, 'cover_uri') and track.cover_uri else None
                    
                    tracks.append({
                        'id': f"yandex_{track.id}",
                        'title': track.title,
                        'artists': [artist.name for artist in track.artists],
                        'duration': track.duration_ms,
                        'cover_uri': cover_uri
                    })
                except:
                    continue
            
            cover_uri = f"https://{playlist.cover_uri.replace('%%', '400x400')}" if hasattr(playlist, 'cover_uri') and playlist.cover_uri else None
            
            return jsonify({
                'id': f"yandex_{playlist.kind}",
                'title': playlist.title,
                'track_count': playlist.track_count,
                'cover_uri': cover_uri,
                'tracks': tracks,
                'service': 'yandex'
            })
        except Exception as e:
            logger.error(f"Yandex playlist error: {e}")
            return jsonify({'error': str(e)}), 500
    
    elif service == 'vk':
        vk_client = get_vk_client(user.id)
        if not vk_client:
            return jsonify({'error': 'Токен VK не настроен'}), 400
        
        try:
            playlist = vk_client.audio.getPlaylistById(playlist_id=int(playlist_id))
            tracks = vk_client.audio.get(playlist_id=int(playlist_id))
            
            track_list = []
            if 'items' in tracks:
                for track in tracks['items']:
                    track_list.append({
                        'id': f"vk_{track['id']}",
                        'title': track['title'],
                        'artists': [track['artist']],
                        'duration': track['duration'] * 1000,
                        'cover_uri': track.get('album', {}).get('thumb', {}).get('photo_300'),
                        'service': 'vk'
                    })
            
            return jsonify({
                'id': f"vk_{playlist['id']}",
                'title': playlist['title'],
                'track_count': playlist['count'],
                'cover_uri': playlist.get('photo', {}).get('photo_300'),
                'tracks': track_list,
                'service': 'vk'
            })
        except Exception as e:
            logger.error(f"VK playlist error: {e}")
            return jsonify({'error': str(e)}), 500
    
    return jsonify({'error': 'Неизвестный сервис'}), 400

# Лайкнутые треки
@app.route('/api/liked')
@login_required
@cache_response(timeout=180)
@api_logged
def get_liked_tracks():
    user = User.query.get(session['user_id'])
    service = user.settings.music_service if user.settings else 'yandex'
    
    tracks = []
    
    if service == 'yandex':
        client = get_yandex_client(user.id)
        if client:
            try:
                liked_tracks = client.users_likes_tracks()
                for track_short in liked_tracks[:50]:
                    try:
                        track = track_short.fetch_track()
                        cover_uri = f"https://{track.cover_uri.replace('%%', '300x300')}" if hasattr(track, 'cover_uri') and track.cover_uri else None
                        
                        tracks.append({
                            'id': f"yandex_{track.id}",
                            'title': track.title,
                            'artists': [artist.name for artist in track.artists],
                            'duration': track.duration_ms,
                            'cover_uri': cover_uri,
                            'service': 'yandex'
                        })
                    except:
                        continue
            except Exception as e:
                logger.error(f"Yandex liked tracks error: {e}")
    
    elif service == 'vk':
        vk_client = get_vk_client(user.id)
        if vk_client:
            try:
                liked_tracks = vk_client.audio.get(count=50)
                if 'items' in liked_tracks:
                    for track in liked_tracks['items']:
                        tracks.append({
                            'id': f"vk_{track['id']}",
                            'title': track['title'],
                            'artists': [track['artist']],
                            'duration': track['duration'] * 1000,
                            'cover_uri': track.get('album', {}).get('thumb', {}).get('photo_300'),
                            'service': 'vk'
                        })
            except Exception as e:
                logger.error(f"VK liked tracks error: {e}")
    
    return jsonify(tracks)

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

# История прослушивания
@app.route('/api/history')
@login_required
@api_logged
def get_history():
    user = User.query.get(session['user_id'])
    
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    
    history = ListeningHistory.query.filter_by(user_id=user.id)\
        .order_by(ListeningHistory.played_at.desc())\
        .paginate(page=page, per_page=per_page, error_out=False)
    
    result = []
    for item in history.items:
        try:
            track_data = json.loads(item.track_data) if item.track_data else {}
            result.append({
                'id': item.id,
                'track_id': item.track_id,
                'track_data': track_data,
                'played_at': item.played_at.isoformat() if item.played_at else None,
                'service': item.service
            })
        except:
            continue
    
    return jsonify({
        'history': result,
        'total': history.total,
        'pages': history.pages,
        'current_page': history.page
    })

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

@app.route('/api/friends/add/<int:friend_id>', methods=['POST'])
@login_required
@api_logged
def add_friend(friend_id):
    user = User.query.get(session['user_id'])
    
    if user.id == friend_id:
        return jsonify({'success': False, 'message': 'Нельзя добавить себя в друзья'})
    
    # Проверяем существующую заявку
    existing = Friend.query.filter(
        ((Friend.user_id == user.id) & (Friend.friend_id == friend_id)) |
        ((Friend.user_id == friend_id) & (Friend.friend_id == user.id))
    ).first()
    
    if existing:
        return jsonify({'success': False, 'message': 'Заявка уже существует'})
    
    # Создаем заявку
    friend_request = Friend(
        user_id=user.id,
        friend_id=friend_id,
        status='pending'
    )
    db.session.add(friend_request)
    db.session.commit()
    
    return jsonify({'success': True, 'message': 'Заявка отправлена'})

# Темы оформления
@app.route('/api/themes', methods=['GET', 'POST'])
@login_required
@api_logged
def themes():
    user = User.query.get(session['user_id'])
    
    if request.method == 'GET':
        user_themes = UserTheme.query.filter_by(user_id=user.id).all()
        
        # Стандартные темы
        default_themes = {
            'dark': {
                'name': 'Темная',
                'colors': {
                    'bgPrimary': '#0a0a0a',
                    'bgSecondary': '#141414',
                    'textPrimary': '#ffffff',
                    'textSecondary': '#b3b3b3',
                    'accent': '#ff6b6b'
                }
            },
            'light': {
                'name': 'Светлая',
                'colors': {
                    'bgPrimary': '#ffffff',
                    'bgSecondary': '#f5f5f5',
                    'textPrimary': '#000000',
                    'textSecondary': '#666666',
                    'accent': '#1976d2'
                }
            }
        }
        
        return jsonify({
            'user_themes': [{
                'id': theme.id,
                'name': theme.name,
                'colors': json.loads(theme.colors),
                'background_url': theme.background_url,
                'is_default': theme.is_default
            } for theme in user_themes],
            'default_themes': default_themes
        })
    
    elif request.method == 'POST':
        data = request.get_json()
        
        theme = UserTheme(
            user_id=user.id,
            name=data['name'],
            colors=json.dumps(data['colors']),
            background_url=data.get('background_url')
        )
        db.session.add(theme)
        db.session.commit()
        
        return jsonify({'success': True, 'theme_id': theme.id})

# Админ-панель
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
    
    return jsonify({
        'users': {
            'total': total_users,
            'active_today': active_users,
            'new_today': User.query.filter(User.created_at >= datetime.utcnow().date()).count()
        },
        'shop': {
            'total_items': total_items,
            'total_sales': total_sales,
            'revenue': total_sales * 10  # Примерная выручка
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
            'is_admin': user.is_admin,
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

# Telegram API маршруты
@app.route('/api/telegram/link', methods=['POST'])
@login_required
@api_logged
def link_telegram_account():
    """Привязка Telegram аккаунта к существующему пользователю"""
    user = User.query.get(session['user_id'])
    data = request.get_json()
    
    telegram_code = data.get('telegram_code', '').strip().upper()
    
    if not telegram_code:
        return jsonify({'success': False, 'message': 'Введите код'})
    
    # Ищем сессию с этим кодом
    telegram_session = TelegramSession.query.filter_by(
        session_data=json.dumps({'verification_code': telegram_code})
    ).first()
    
    if not telegram_session:
        # Попробуем найти по части JSON
        sessions = TelegramSession.query.all()
        for session in sessions:
            try:
                if session.session_data:
                    data = json.loads(session.session_data)
                    if data.get('verification_code') == telegram_code:
                        telegram_session = session
                        break
            except:
                continue
    
    if not telegram_session:
        return jsonify({'success': False, 'message': 'Неверный код'})
    
    # Проверяем срок действия
    if telegram_session.last_active and \
       telegram_session.last_active < datetime.utcnow() - timedelta(minutes=10):
        return jsonify({'success': False, 'message': 'Код истек'})
    
    # Проверяем, не привязан ли уже этот Telegram
    existing_user = User.query.filter_by(telegram_id=telegram_session.telegram_id).first()
    if existing_user:
        return jsonify({'success': False, 'message': 'Этот Telegram уже привязан к другому аккаунту'})
    
    # Привязываем Telegram
    user.telegram_id = telegram_session.telegram_id
    user.telegram_username = telegram_session.username
    user.telegram_verified = True
    
    telegram_session.user_id = user.id
    telegram_session.session_data = None
    
    db.session.commit()
    
    # Отправляем уведомление
    if telegram_bot:
        try:
            import asyncio
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            async def send_notification():
                try:
                    await telegram_bot.bot_app.bot.send_message(
                        chat_id=telegram_session.chat_id,
                        text=f"✅ Telegram успешно привязан!\n\n"
                             f"Аккаунт: {user.username}\n"
                             f"Баланс: {user.currency.balance if user.currency else 0} монет\n\n"
                             f"Теперь ты можешь:\n"
                             f"• Получать уведомления\n"
                             f"• Использовать команды бота\n"
                             f"• Получать ежедневные награды",
                        parse_mode="Markdown"
                    )
                except Exception as e:
                    logger.error(f"Failed to send Telegram notification: {e}")
            
            loop.run_until_complete(send_notification())
        except Exception as e:
            logger.error(f"Error sending Telegram notification: {e}")
    
    return jsonify({
        'success': True,
        'message': 'Telegram успешно привязан',
        'telegram_username': user.telegram_username
    })

# Статические файлы
@app.route('/static/<path:filename>')
def static_files(filename):
    return send_from_directory('static', filename)

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
            'telegram_bot': 'active' if telegram_bot else 'disabled'
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
    
    app.run(host='0.0.0.0', port=port, debug=debug)