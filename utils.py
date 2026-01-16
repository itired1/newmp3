import os
import uuid
import bcrypt
import smtplib
import logging
import requests
import secrets
from datetime import datetime, timedelta
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from PIL import Image
from io import BytesIO
import base64
import random
import re
import json
from collections import Counter
from functools import wraps, lru_cache
from flask import session, jsonify, request, g, current_app
from yandex_music import Client
import vk_api
import redis
from redis.exceptions import ConnectionError as RedisConnectionError
import hashlib
import qrcode
import io

logger = logging.getLogger(__name__)

# Конфигурация Telegram бота
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
TELEGRAM_API_URL = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"
SERVER_URL = os.getenv('SERVER_URL', 'http://localhost:5001')

# Конфигурация SMTP
SMTP_CONFIG = {
    'host': os.getenv('SMTP_HOST', 'smtp.gmail.com'),
    'port': int(os.getenv('SMTP_PORT', 587)),
    'username': os.getenv('SMTP_USERNAME'),
    'password': os.getenv('SMTP_PASSWORD'),
    'from_email': os.getenv('SMTP_FROM_EMAIL', 'noreply@itired.com'),
    'from_name': os.getenv('SMTP_FROM_NAME', 'itired Music Platform')
}

# Конфигурация загрузки файлов
UPLOAD_CONFIG = {
    'max_size_mb': 16,
    'allowed_extensions': {'png', 'jpg', 'jpeg', 'gif', 'webp', 'svg', 'mp3', 'wav', 'ogg', 'mp4', 'avi', 'mov'},
    'image_formats': {'png', 'jpg', 'jpeg', 'gif', 'webp', 'svg'},
    'audio_formats': {'mp3', 'wav', 'ogg'},
    'video_formats': {'mp4', 'avi', 'mov'}
}

# --- Redis для кэширования ---
redis_client = None
try:
    redis_url = os.getenv('REDIS_URL', 'redis://localhost:6379/0')
    redis_client = redis.from_url(redis_url, decode_responses=True, socket_connect_timeout=5)
    redis_client.ping()
    logger.info("Redis подключен успешно")
except (RedisConnectionError, redis.exceptions.ConnectionError, redis.exceptions.TimeoutError) as e:
    logger.warning(f"Redis недоступен, используется in-memory кэш: {e}")
    redis_client = None

# --- Вспомогательные функции ---
def generate_token(length=32):
    """Генерация токена"""
    return secrets.token_hex(length)

def generate_code(length=6):
    """Генерация числового кода"""
    return ''.join(random.choices('0123456789', k=length))

def generate_qr_code(data, size=10):
    """Генерация QR кода"""
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=size,
        border=4,
    )
    qr.add_data(data)
    qr.make(fit=True)
    
    img = qr.make_image(fill_color="black", back_color="white")
    img_bytes = io.BytesIO()
    img.save(img_bytes, format='PNG')
    img_bytes.seek(0)
    
    return img_bytes

# --- Функции для работы с Telegram ---
def send_telegram_message(chat_id, text, parse_mode='Markdown', disable_web_page_preview=True):
    """Отправка сообщения через Telegram бота"""
    if not TELEGRAM_BOT_TOKEN:
        logger.warning("Telegram bot token not set")
        return False
    
    try:
        url = f"{TELEGRAM_API_URL}/sendMessage"
        payload = {
            'chat_id': chat_id,
            'text': text,
            'parse_mode': parse_mode,
            'disable_web_page_preview': disable_web_page_preview
        }
        
        response = requests.post(url, json=payload, timeout=10)
        if response.status_code == 200:
            return True
        else:
            logger.error(f"Telegram API error: {response.status_code} - {response.text}")
            return False
    except Exception as e:
        logger.error(f"Telegram send error: {e}")
        return False

def send_telegram_photo(chat_id, photo_url, caption=None):
    """Отправка фото через Telegram"""
    if not TELEGRAM_BOT_TOKEN:
        return False
    
    try:
        url = f"{TELEGRAM_API_URL}/sendPhoto"
        payload = {
            'chat_id': chat_id,
            'photo': photo_url,
            'caption': caption,
            'parse_mode': 'Markdown'
        }
        
        response = requests.post(url, json=payload, timeout=10)
        return response.status_code == 200
    except Exception as e:
        logger.error(f"Telegram photo send error: {e}")
        return False

def send_telegram_document(chat_id, document_url, caption=None):
    """Отправка документа через Telegram"""
    if not TELEGRAM_BOT_TOKEN:
        return False
    
    try:
        url = f"{TELEGRAM_API_URL}/sendDocument"
        payload = {
            'chat_id': chat_id,
            'document': document_url,
            'caption': caption
        }
        
        response = requests.post(url, json=payload, timeout=10)
        return response.status_code == 200
    except Exception as e:
        logger.error(f"Telegram document send error: {e}")
        return False

def get_telegram_user_info(user_id):
    """Получение информации о пользователе Telegram"""
    if not TELEGRAM_BOT_TOKEN:
        return None
    
    try:
        url = f"{TELEGRAM_API_URL}/getChat"
        payload = {
            'chat_id': user_id
        }
        
        response = requests.post(url, json=payload, timeout=10)
        if response.status_code == 200:
            return response.json().get('result', {})
        return None
    except Exception as e:
        logger.error(f"Telegram get user info error: {e}")
        return None

def create_telegram_login_url(bot_username, redirect_url=None):
    """Создание URL для входа через Telegram"""
    bot_username = bot_username.lstrip('@')
    
    if redirect_url:
        # Создаем кнопку для входа через Telegram
        return f"https://t.me/{bot_username}?start={hashlib.md5(redirect_url.encode()).hexdigest()}"
    else:
        return f"https://t.me/{bot_username}"

def send_telegram_notification(user_id, title, message, notification_type='info'):
    """Отправка уведомления через Telegram"""
    from models import User
    
    user = User.query.get(user_id)
    if not user or not user.telegram_id:
        return False
    
    # Определяем эмодзи по типу уведомления
    emoji_map = {
        'info': 'ℹ️',
        'success': '✅',
        'warning': '⚠️',
        'error': '❌',
        'gift': '🎁',
        'money': '💰',
        'music': '🎵',
        'shop': '🛍️',
        'friend': '👥',
        'system': '🔧'
    }
    
    emoji = emoji_map.get(notification_type, '📢')
    
    formatted_message = f"{emoji} *{title}*\n\n{message}\n\n_Отправлено {datetime.now().strftime('%d.%m.%Y %H:%M')}_"
    
    return send_telegram_message(user.telegram_id, formatted_message)

# --- Функции для работы с файлами ---
def save_uploaded_file(file_data, file_type='avatar', filename=None):
    """Сохранение загруженного файла с оптимизацией"""
    try:
        # Определяем папку для сохранения
        if file_type == 'avatar':
            folder = 'avatars'
            max_size = (400, 400)
            quality = 85
        elif file_type == 'banner':
            folder = 'banners'
            max_size = (1200, 300)
            quality = 90
        elif file_type == 'shop_item':
            folder = 'shop_items'
            max_size = (800, 800)
            quality = 90
        elif file_type == 'music_cover':
            folder = 'covers'
            max_size = (500, 500)
            quality = 90
        else:
            folder = 'others'
            max_size = (1024, 1024)
            quality = 85
        
        upload_dir = os.path.join('static', 'uploads', folder)
        os.makedirs(upload_dir, exist_ok=True)
        
        # Генерация имени файла
        if not filename:
            file_ext = 'jpg' if file_type in ['avatar', 'banner', 'shop_item', 'music_cover'] else 'bin'
            filename = f"{uuid.uuid4().hex}.{file_ext}"
        
        filepath = os.path.join(upload_dir, filename)
        
        # Обработка изображений
        if file_type in ['avatar', 'banner', 'shop_item', 'music_cover']:
            image = Image.open(BytesIO(file_data))
            
            # Конвертируем RGBA в RGB
            if image.mode in ('RGBA', 'LA'):
                background = Image.new('RGB', image.size, (45, 45, 45))
                background.paste(image, mask=image.split()[-1])
                image = background
            elif image.mode != 'RGB':
                image = image.convert('RGB')
            
            # Оптимизация размера
            image.thumbnail(max_size, Image.Resampling.LANCZOS)
            
            # Сохранение с оптимизацией
            image.save(filepath, 'JPEG', quality=quality, optimize=True, progressive=True)
        else:
            # Сохранение других файлов
            with open(filepath, 'wb') as f:
                f.write(file_data)
        
        return f"/static/uploads/{folder}/{filename}"
    except Exception as e:
        logger.error(f"Error saving uploaded file: {e}")
        return None

def validate_image(file_data, max_size_mb=5):
    """Валидация изображения"""
    try:
        # Проверка размера
        if len(file_data) > max_size_mb * 1024 * 1024:
            return False, f"Размер файла превышает {max_size_mb}MB"
        
        # Проверка формата
        image = Image.open(BytesIO(file_data))
        image.verify()
        
        # Проверка разрешения
        if image.size[0] > 5000 or image.size[1] > 5000:
            return False, "Слишком большое разрешение"
        
        return True, "OK"
    except Exception as e:
        return False, f"Некорректный файл: {str(e)}"

def validate_audio(file_data, max_size_mb=10):
    """Валидация аудио файла"""
    try:
        if len(file_data) > max_size_mb * 1024 * 1024:
            return False, f"Размер файла превышает {max_size_mb}MB"
        
        # Базовые проверки аудио файла
        if len(file_data) < 100:  # Минимальный размер для аудио
            return False, "Файл слишком маленький для аудио"
        
        # Проверка сигнатуры файла (MP3, WAV, OGG)
        if file_data[:3] == b'ID3' or file_data[:2] == b'\xff\xfb':
            return True, "OK"  # MP3
        elif file_data[:4] == b'RIFF':
            return True, "OK"  # WAV
        elif file_data[:4] == b'OggS':
            return True, "OK"  # OGG
        
        return False, "Неподдерживаемый формат аудио"
    except Exception as e:
        return False, f"Ошибка валидации аудио: {str(e)}"

# --- Email функции ---
def send_email(to_email, subject, body_html, body_text=None):
    """Отправка email"""
    if not all([SMTP_CONFIG['host'], SMTP_CONFIG['username'], SMTP_CONFIG['password']]):
        logger.warning("SMTP not configured")
        return False
    
    try:
        msg = MIMEMultipart('alternative')
        msg['From'] = f"{SMTP_CONFIG['from_name']} <{SMTP_CONFIG['from_email']}>"
        msg['To'] = to_email
        msg['Subject'] = subject
        
        if body_text:
            part1 = MIMEText(body_text, 'plain', 'utf-8')
            msg.attach(part1)
        
        part2 = MIMEText(body_html, 'html', 'utf-8')
        msg.attach(part2)
        
        server = smtplib.SMTP(SMTP_CONFIG['host'], SMTP_CONFIG['port'])
        server.starttls()
        server.login(SMTP_CONFIG['username'], SMTP_CONFIG['password'])
        server.send_message(msg)
        server.quit()
        
        logger.info(f"Email sent to {to_email}")
        return True
    except Exception as e:
        logger.error(f"Error sending email: {e}")
        return False

def send_verification_email(email, verification_code):
    """Отправка кода подтверждения"""
    subject = "🎵 Код подтверждения для itired"
    
    body_html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <style>
            body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
            .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
            .header {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 20px; text-align: center; border-radius: 10px 10px 0 0; }}
            .content {{ background: #f9f9f9; padding: 30px; border-radius: 0 0 10px 10px; }}
            .code {{ font-size: 32px; font-weight: bold; text-align: center; letter-spacing: 10px; color: #667eea; margin: 30px 0; }}
            .footer {{ text-align: center; margin-top: 30px; color: #666; font-size: 12px; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>🎵 itired</h1>
                <p>Музыкальная платформа нового поколения</p>
            </div>
            <div class="content">
                <h2>Ваш код подтверждения</h2>
                <p>Используйте этот код для завершения регистрации или подтверждения действия:</p>
                <div class="code">{verification_code}</div>
                <p><strong>Код действителен в течение 10 минут.</strong></p>
                <p>Если вы не запрашивали этот код, проигнорируйте это письмо.</p>
            </div>
            <div class="footer">
                <p>© 2024 itired. Все права защищены.</p>
                <p>Это письмо отправлено автоматически, пожалуйста, не отвечайте на него.</p>
            </div>
        </div>
    </body>
    </html>
    """
    
    body_text = f"Ваш код подтверждения для itired: {verification_code}\nКод действителен 10 минут."
    
    return send_email(email, subject, body_html, body_text)

def send_welcome_email(email, username):
    """Отправка приветственного письма"""
    subject = "🎉 Добро пожаловать в itired!"
    
    body_html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <style>
            body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
            .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
            .header {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 20px; text-align: center; border-radius: 10px 10px 0 0; }}
            .content {{ background: #f9f9f9; padding: 30px; border-radius: 0 0 10px 10px; }}
            .feature {{ margin: 20px 0; padding: 15px; background: white; border-radius: 5px; box-shadow: 0 2px 5px rgba(0,0,0,0.1); }}
            .footer {{ text-align: center; margin-top: 30px; color: #666; font-size: 12px; }}
            .button {{ display: inline-block; padding: 12px 30px; background: #667eea; color: white; text-decoration: none; border-radius: 5px; margin: 20px 0; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>🎵 Добро пожаловать в itired!</h1>
                <p>Привет, {username}!</p>
            </div>
            <div class="content">
                <h2>Мы рады приветствовать вас на нашей музыкальной платформе!</h2>
                
                <div class="feature">
                    <h3>🎧 Бесконечная музыка</h3>
                    <p>Слушайте миллионы треков из Яндекс.Музыки, VK и других сервисов в одном месте.</p>
                </div>
                
                <div class="feature">
                    <h3>💰 Зарабатывайте монеты</h3>
                    <p>Слушайте музыку, получайте ежедневные награды и покупайте уникальный контент в магазине.</p>
                </div>
                
                <div class="feature">
                    <h3>🎨 Кастомизируйте профиль</h3>
                    <p>Покупайте темы, аватары, баннеры и создавайте уникальный стиль своего профиля.</p>
                </div>
                
                <p style="text-align: center;">
                    <a href="{SERVER_URL}" class="button">Начать использование</a>
                </p>
                
                <p>На вашем счету уже есть 100 монет для первых покупок!</p>
            </div>
            <div class="footer">
                <p>© 2024 itired. Все права защищены.</p>
                <p>Если у вас есть вопросы, напишите нам на support@itired.com</p>
            </div>
        </div>
    </body>
    </html>
    """
    
    return send_email(email, subject, body_html)

# --- Декораторы с кэшированием ---
def cache_response(timeout=300):
    """Декоратор для кэширования ответов API"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not redis_client:
                return f(*args, **kwargs)
            
            # Создаем ключ кэша на основе аргументов
            cache_key_parts = [f.__name__]
            
            # Добавляем user_id если есть
            if 'user_id' in session:
                cache_key_parts.append(str(session['user_id']))
            
            # Добавляем аргументы запроса
            cache_key_parts.append(request.path)
            cache_key_parts.append(hash(frozenset(request.args.items())))
            
            cache_key = f"cache:{':'.join(cache_key_parts)}"
            
            # Пробуем получить из кэша
            cached = redis_client.get(cache_key)
            if cached:
                try:
                    return jsonify(json.loads(cached))
                except:
                    pass
            
            # Выполняем функцию
            result = f(*args, **kwargs)
            
            # Кэшируем результат
            try:
                if isinstance(result, tuple):
                    response, status = result
                    if status == 200:
                        redis_client.setex(cache_key, timeout, response.get_data(as_text=True))
                else:
                    redis_client.setex(cache_key, timeout, result.get_data(as_text=True))
            except Exception as e:
                logger.error(f"Cache error: {e}")
            
            return result
        return decorated_function
    return decorator

def invalidate_cache(pattern):
    """Инвалидация кэша по паттерну"""
    if redis_client:
        keys = redis_client.keys(f"cache:{pattern}*")
        if keys:
            redis_client.delete(*keys)

# --- Улучшенные декораторы ---
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return jsonify({'error': 'Требуется авторизация'}), 401
        
        # Обновляем время последней активности
        from models import User, db
        user = User.query.get(session['user_id'])
        if user:
            user.update_last_active()
            db.session.commit()
        
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        from models import User
        user = User.query.get(session.get('user_id'))
        if not user or not user.is_admin:
            return jsonify({'error': 'Требуются права администратора'}), 403
        return f(*args, **kwargs)
    return decorated_function

def rate_limit_by_user(limit="10 per minute"):
    """Rate limit по пользователю"""
    from flask_limiter.util import get_remote_address
    
    def key_func():
        user_id = session.get('user_id')
        if user_id:
            return f"user:{user_id}"
        return get_remote_address()
    
    return key_func

# --- Музыкальные сервисы с кэшированием ---
@lru_cache(maxsize=100)
def get_yandex_client_cached(token):
    """Кэшированный клиент Яндекс.Музыки"""
    try:
        client = Client(token).init()
        return client
    except Exception as e:
        logger.error(f"Error initializing Yandex Music client: {e}")
        return None

def get_yandex_client(user_id=None):
    try:
        from models import User
        
        if user_id:
            user = User.query.get(user_id)
            token = user.yandex_token if user else None
        else:
            user = User.query.get(session.get('user_id'))
            token = user.yandex_token if user else None
        
        if not token:
            return None
        
        return get_yandex_client_cached(token)
    except Exception as e:
        logger.error(f"Error getting Yandex client: {e}")
        return None

@lru_cache(maxsize=100)
def get_vk_client_cached(token):
    """Кэшированный клиент VK"""
    try:
        if 'access_token=' in token:
            match = re.search(r'access_token=([^&]+)', token)
            if match:
                token = match.group(1)
        
        session_vk = vk_api.VkApi(token=token)
        return session_vk.get_api()
    except Exception as e:
        logger.error(f"Error initializing VK client: {e}")
        return None

def get_vk_client(user_id=None):
    try:
        from models import User
        
        if user_id:
            user = User.query.get(user_id)
            token = user.vk_token if user else None
        else:
            user = User.query.get(session.get('user_id'))
            token = user.vk_token if user else None
        
        if not token:
            return None
        
        return get_vk_client_cached(token)
    except Exception as e:
        logger.error(f"Error getting VK client: {e}")
        return None

# --- Валютная система ---
def add_currency(user_id, amount, reason, metadata=None):
    try:
        from models import db, UserCurrency, CurrencyTransaction, UserStatistic
        
        currency = UserCurrency.query.filter_by(user_id=user_id).first()
        
        if currency:
            currency.balance += amount
            if amount > 0:
                currency.total_earned += amount
            else:
                currency.total_spent += abs(amount)
        else:
            currency = UserCurrency(
                user_id=user_id, 
                balance=amount,
                total_earned=amount if amount > 0 else 0,
                total_spent=abs(amount) if amount < 0 else 0
            )
            db.session.add(currency)
        
        transaction = CurrencyTransaction(
            user_id=user_id,
            amount=amount,
            reason=reason,
            transaction_metadata=json.dumps(metadata) if metadata else None
        )
        db.session.add(transaction)
        
        # Обновляем статистику
        if reason == 'daily_reward':
            stat = UserStatistic.query.filter_by(user_id=user_id).first()
            if not stat:
                stat = UserStatistic(user_id=user_id)
                db.session.add(stat)
            stat.daily_rewards_claimed += 1
            stat.last_daily_reward = datetime.utcnow()
        
        db.session.commit()
        
        # Инвалидация кэша баланса
        invalidate_cache(f"*{user_id}*")
        
        return True
    except Exception as e:
        logger.error(f"Error adding currency: {e}")
        return False

# --- Рекомендательная система с кэшированием ---
class EnhancedRecommender:
    def __init__(self):
        self.cache_timeout = 1800  # 30 минут
        
    def get_enhanced_recommendations(self, user_id, service='yandex'):
        """Получение рекомендаций с кэшированием"""
        if redis_client:
            cache_key = f"recommendations:{user_id}:{service}"
            cached = redis_client.get(cache_key)
            if cached:
                return json.loads(cached)
        
        recommendations = self._get_recommendations(user_id, service)
        
        if redis_client and recommendations:
            redis_client.setex(cache_key, self.cache_timeout, json.dumps(recommendations))
        
        return recommendations
    
    def _get_recommendations(self, user_id, service='yandex'):
        recommendations = []
        
        try:
            if service == 'yandex':
                client = get_yandex_client(user_id)
                if client:
                    # Кэшированные запросы для истории
                    history_recs = self._get_cached_history_recommendations(user_id, client)
                    recommendations.extend(history_recs)
                    
                    liked_recs = self._get_liked_based_recommendations(user_id, client)
                    recommendations.extend(liked_recs)
                    
                    if not recommendations:
                        fallback_recs = self._get_fallback_recommendations(client)
                        recommendations.extend(fallback_recs)
            
            elif service == 'vk':
                vk_client = get_vk_client(user_id)
                if vk_client:
                    vk_recs = self._get_vk_recommendations(vk_client)
                    recommendations.extend(vk_recs)
            
            return self._deduplicate_and_shuffle(recommendations)
            
        except Exception as e:
            logger.error(f"Enhanced recommendations error: {e}")
            return []
    
    def _get_cached_history_recommendations(self, user_id, client):
        """Кэшированные рекомендации на основе истории"""
        from models import ListeningHistory
        try:
            # Получаем последние 20 треков из истории
            history = ListeningHistory.query.filter_by(
                user_id=user_id
            ).order_by(
                ListeningHistory.played_at.desc()
            ).limit(20).all()
            
            if not history:
                return []
            
            recommendations = []
            
            # Анализируем жанры и исполнителей
            genres = Counter()
            artists = Counter()
            
            for h in history:
                try:
                    track_data = json.loads(h.track_data) if h.track_data else {}
                    if 'genre' in track_data:
                        genres[track_data['genre']] += 1
                    if 'artists' in track_data:
                        for artist in track_data['artists']:
                            artists[artist] += 1
                except:
                    continue
            
            # Получаем рекомендации по топ жанрам
            for genre, _ in genres.most_common(2):
                try:
                    search_results = client.search(f"жанр:{genre}", type_='track')
                    if search_results and search_results.tracks:
                        for track in search_results.tracks.results[:2]:
                            recommendations.append(self._format_track(track, 'history_genre'))
                except:
                    continue
            
            # Получаем рекомендации по топ исполнителям
            for artist, _ in artists.most_common(2):
                try:
                    search_results = client.search(artist, type_='track')
                    if search_results and search_results.tracks:
                        for track in search_results.tracks.results[:2]:
                            if not any(t['id'] == f"yandex_{track.id}" for t in recommendations):
                                recommendations.append(self._format_track(track, 'history_artist'))
                except:
                    continue
            
            return recommendations
            
        except Exception as e:
            logger.error(f"Cached history recommendations error: {e}")
            return []
    
    def _get_liked_based_recommendations(self, user_id, client):
        try:
            liked_tracks = client.users_likes_tracks()
            if not liked_tracks:
                return []
            
            recommendations = []
            sample_size = min(3, len(liked_tracks))
            sample_tracks = random.sample(list(liked_tracks[:10]), sample_size)
            
            for track_short in sample_tracks:
                try:
                    track = track_short.fetch_track()
                    # Ищем похожие треки
                    if track.artists:
                        search_query = f"{track.title} {track.artists[0].name}"
                        similar_tracks = client.search(search_query, type_='track')
                        
                        if similar_tracks and similar_tracks.tracks:
                            for similar in similar_tracks.tracks.results[:2]:
                                if similar.id != track.id:
                                    recommendations.append(self._format_track(similar, 'liked_similar'))
                except:
                    continue
            
            return recommendations
            
        except Exception as e:
            logger.error(f"Liked based recommendations error: {e}")
            return []
    
    def _get_fallback_recommendations(self, client):
        recommendations = []
        
        try:
            # Новые релизы
            new_releases = client.new_releases()
            if new_releases and hasattr(new_releases, 'new_releases'):
                for album in new_releases.new_releases[:3]:
                    recommendations.append({
                        'id': f"yandex_{album.id}",
                        'title': album.title,
                        'type': 'album',
                        'artists': [artist.name for artist in album.artists],
                        'cover_uri': f"https://{album.cover_uri.replace('%%', '300x300')}" if hasattr(album, 'cover_uri') and album.cover_uri else None,
                        'source': 'new_releases'
                    })
            
            # Чарты
            chart = client.chart('world')
            if chart and hasattr(chart, 'chart') and chart.chart.tracks:
                for track in chart.chart.tracks[:3]:
                    recommendations.append(self._format_track(track, 'chart'))
                    
        except Exception as e:
            logger.error(f"Fallback recommendations error: {e}")
        
        return recommendations
    
    def _get_vk_recommendations(self, vk_client):
        try:
            recommendations = []
            vk_recs = vk_client.audio.getRecommendations(count=6)
            
            if 'items' in vk_recs:
                for track in vk_recs['items']:
                    recommendations.append({
                        'id': f"vk_{track['id']}",
                        'title': track['title'],
                        'type': 'track',
                        'artists': [track['artist']],
                        'cover_uri': track.get('album', {}).get('thumb', {}).get('photo_300') if track.get('album') else None,
                        'duration': track['duration'] * 1000,
                        'source': 'vk_recommendations'
                    })
            
            return recommendations
            
        except Exception as e:
            logger.error(f"VK recommendations error: {e}")
            return []
    
    def _format_track(self, track, source):
        cover_uri = None
        if hasattr(track, 'cover_uri') and track.cover_uri:
            cover_uri = f"https://{track.cover_uri.replace('%%', '300x300')}"
        
        return {
            'id': f"yandex_{track.id}",
            'title': track.title,
            'type': 'track',
            'artists': [artist.name for artist in track.artists] if hasattr(track, 'artists') else [],
            'cover_uri': cover_uri,
            'album': track.albums[0].title if track.albums else 'Unknown Album',
            'duration': getattr(track, 'duration_ms', 0),
            'source': source
        }
    
    def _deduplicate_and_shuffle(self, recommendations):
        seen_ids = set()
        unique_recommendations = []
        
        for rec in recommendations:
            if rec['id'] not in seen_ids:
                seen_ids.add(rec['id'])
                unique_recommendations.append(rec)
        
        random.shuffle(unique_recommendations)
        return unique_recommendations[:8]

# Глобальные экземпляры
recommender = EnhancedRecommender()

# --- Функции для кэширования в БД ---
def cache_db_set(key, value, expires_in=300):
    """Кэширование в базу данных"""
    try:
        from models import db, CacheItem
        expires_at = datetime.utcnow() + timedelta(seconds=expires_in)
        
        cache_item = CacheItem.query.filter_by(key=key).first()
        if cache_item:
            cache_item.value = value
            cache_item.expires_at = expires_at
        else:
            cache_item = CacheItem(key=key, value=value, expires_at=expires_at)
            db.session.add(cache_item)
        
        db.session.commit()
        return True
    except Exception as e:
        logger.error(f"DB cache set error: {e}")
        return False

def cache_db_get(key):
    """Получение из кэша базы данных"""
    try:
        from models import CacheItem
        cache_item = CacheItem.query.filter_by(key=key).first()
        
        if cache_item and cache_item.expires_at > datetime.utcnow():
            return cache_item.value
        elif cache_item:
            # Удаляем просроченный кэш
            from models import db
            db.session.delete(cache_item)
            db.session.commit()
        
        return None
    except Exception as e:
        logger.error(f"DB cache get error: {e}")
        return None

def clean_expired_cache():
    """Очистка просроченного кэша"""
    try:
        from models import db, CacheItem
        expired = CacheItem.query.filter(CacheItem.expires_at <= datetime.utcnow()).all()
        for item in expired:
            db.session.delete(item)
        db.session.commit()
        return len(expired)
    except Exception as e:
        logger.error(f"Clean cache error: {e}")
        return 0

# --- Статистика и мониторинг ---
def log_api_request(endpoint, method, user_id=None, status_code=200, response_time=0):
    """Логирование API запросов"""
    try:
        from models import db, APILog
        
        # Ограничиваем размер данных
        request_data = None
        if request.is_json:
            try:
                data = request.get_json()
                request_data = json.dumps(data)[:5000]  # Ограничиваем размер
            except:
                pass
        
        log = APILog(
            endpoint=endpoint,
            method=method,
            user_id=user_id,
            ip_address=request.remote_addr,
            status_code=status_code,
            response_time=response_time,
            request_data=request_data,
            user_agent=request.user_agent.string[:500]
        )
        db.session.add(log)
        db.session.commit()
    except Exception as e:
        logger.error(f"API log error: {e}")

def get_api_stats(timeframe='day'):
    """Статистика API запросов"""
    try:
        from models import APILog, db
        from sqlalchemy import func, case
        
        time_filter = {
            'hour': func.datetime('now', '-1 hour'),
            'day': func.date('now'),
            'week': func.datetime('now', '-7 days'),
            'month': func.datetime('now', '-30 days')
        }.get(timeframe, func.date('now'))
        
        stats = db.session.query(
            APILog.endpoint,
            func.count(APILog.id).label('count'),
            func.avg(APILog.response_time).label('avg_time'),
            func.sum(case((APILog.status_code >= 400, 1), else_=0)).label('errors')
        ).filter(
            APILog.created_at >= time_filter
        ).group_by(
            APILog.endpoint
        ).all()
        
        return [
            {
                'endpoint': s.endpoint,
                'count': s.count,
                'avg_time': float(s.avg_time or 0),
                'errors': s.errors
            }
            for s in stats
        ]
    except Exception as e:
        logger.error(f"API stats error: {e}")
        return []