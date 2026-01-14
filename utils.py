import os
import uuid
import bcrypt
import smtplib
import logging
import requests
import secrets
from datetime import datetime, timedelta
from email.mime.text import MIMEText
from PIL import Image
from io import BytesIO
import base64
import random
import re
import json
from collections import Counter
from functools import wraps, lru_cache
from flask import session, jsonify, request, g
from yandex_music import Client
import vk_api
import redis  # Установите pip install redis
from redis.exceptions import ConnectionError as RedisConnectionError
from sqlalchemy import case  # Добавьте этот импорт

logger = logging.getLogger(__name__)

# --- Конфигурация из переменных окружения ---
EMAIL_CONFIG = {
    'smtp_server': os.getenv('SMTP_SERVER', 'smtp.gmail.com'),
    'smtp_port': int(os.getenv('SMTP_PORT', 587)),
    'email': os.getenv('SMTP_EMAIL'),
    'password': os.getenv('SMTP_PASSWORD')
}

UPLOAD_FOLDER = 'static/uploads'
os.makedirs(os.path.join(UPLOAD_FOLDER, 'avatars'), exist_ok=True)
os.makedirs(os.path.join(UPLOAD_FOLDER, 'banners'), exist_ok=True)

# --- Redis для кэширования ---
redis_client = None
try:
    redis_url = os.getenv('REDIS_URL', 'redis://localhost:6379/0')
    redis_client = redis.from_url(redis_url, decode_responses=True)
    redis_client.ping()
    logger.info("Redis подключен успешно")
except (RedisConnectionError, redis.exceptions.ConnectionError):
    logger.warning("Redis недоступен, используется in-memory кэш")
    redis_client = None

# --- Декораторы с кэшированием ---
def cache_response(timeout=300):
    """Декоратор для кэширования ответов API"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not redis_client:
                return f(*args, **kwargs)
            
            # Создаем ключ кэша на основе аргументов
            cache_key = f"cache:{request.path}:{hash(frozenset(request.args.items()))}"
            
            # Пробуем получить из кэша
            cached = redis_client.get(cache_key)
            if cached:
                return jsonify(json.loads(cached))
            
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

# --- Функции работы с файлами ---
def save_uploaded_file(file_data, file_type='avatar'):
    """Сохранение загруженного файла с оптимизацией"""
    try:
        if file_type == 'avatar':
            folder = 'avatars'
            max_size = (400, 400)
        elif file_type == 'banner':
            folder = 'banners'
            max_size = (1200, 300)
        else:
            folder = 'others'
            max_size = (800, 800)
        
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
        
        # Генерация имени файла
        unique_filename = f"{uuid.uuid4().hex}.jpg"
        filepath = os.path.join(UPLOAD_FOLDER, folder, unique_filename)
        
        # Сохранение с оптимизацией
        image.save(filepath, 'JPEG', quality=85, optimize=True, progressive=True)
        
        return f"/static/uploads/{folder}/{unique_filename}"
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

# --- Email функции ---
def send_verification_email(email, verification_code):
    try:
        msg = MIMEText(f'Ваш код подтверждения: {verification_code}\nДействует 10 минут.', 'plain', 'utf-8')
        msg['From'] = f"itired 🎵 <{EMAIL_CONFIG['email']}>"
        msg['To'] = email
        msg['Subject'] = '🎵 Ваш код подтверждения для itired'
        
        server = smtplib.SMTP(EMAIL_CONFIG['smtp_server'], EMAIL_CONFIG['smtp_port'])
        server.starttls()
        server.login(EMAIL_CONFIG['email'], EMAIL_CONFIG['password'])
        server.send_message(msg)
        server.quit()
        
        logger.info(f"Письмо отправлено на {email}")
        return True
    except Exception as e:
        logger.error(f"Ошибка отправки письма: {e}")
        return False

def send_notification_email(email, subject, message):
    """Отправка уведомлений"""
    try:
        msg = MIMEText(message, 'plain', 'utf-8')
        msg['From'] = f"itired 🎵 <{EMAIL_CONFIG['email']}>"
        msg['To'] = email
        msg['Subject'] = subject
        
        server = smtplib.SMTP(EMAIL_CONFIG['smtp_server'], EMAIL_CONFIG['smtp_port'])
        server.starttls()
        server.login(EMAIL_CONFIG['email'], EMAIL_CONFIG['password'])
        server.send_message(msg)
        server.quit()
        
        return True
    except Exception as e:
        logger.error(f"Ошибка отправки уведомления: {e}")
        return False

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
            metadata=json.dumps(metadata) if metadata else None
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
        invalidate_cache(f"currency:{user_id}")
        
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
                    track_data = json.loads(h.track_data)
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
        log = APILog(
            endpoint=endpoint,
            method=method,
            user_id=user_id,
            ip_address=request.remote_addr,
            status_code=status_code,
            response_time=response_time
        )
        db.session.add(log)
        db.session.commit()
    except Exception as e:
        logger.error(f"API log error: {e}")

def get_api_stats(timeframe='day'):
    """Статистика API запросов"""
    try:
        from models import APILog, db
        from sqlalchemy import func
        
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