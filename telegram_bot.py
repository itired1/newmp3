import os
import logging
import json
from datetime import datetime, timedelta
import threading
import random
import string
import asyncio
import requests
from typing import Optional, Dict, List

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
    ContextTypes,
    ConversationHandler
)
from telegram.constants import ParseMode, ChatAction

logger = logging.getLogger(__name__)

# URL сервера
SERVER_URL = os.getenv('SERVER_URL', 'http://localhost:5001')
BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')

# Состояния для диалогов
AWAITING_CODE, AWAITING_CONFIRMATION = range(2)

class TelegramBot:
    def __init__(self, token: str):
        self.token = token
        self.bot_app = None
        self.active_codes = {}  # telegram_id -> code_data
        self.user_states = {}   # telegram_id -> state
        
    def generate_code(self, length=6) -> str:
        """Генерация кода подтверждения"""
        return ''.join(random.choices(string.ascii_uppercase + string.digits, k=length))
    
    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /start"""
        user = update.effective_user
        
        welcome_text = (
            f"🎵 *Добро пожаловать в itired!*\n\n"
            f"Я — официальный бот музыкальной платформы itired.\n\n"
            f"*Что я умею:*\n"
            f"🔗 Привязывать аккаунт Telegram к itired\n"
            f"💰 Проверять баланс монет\n"
            f"🎁 Выдавать ежедневные награды\n"
            f"🎧 Получать музыкальные рекомендации\n"
            f"🔔 Получать уведомления о событиях\n\n"
            f"*Основные команды:*\n"
            f"/link - привязать аккаунт\n"
            f"/code - получить код для регистрации\n"
            f"/balance - проверить баланс\n"
            f"/daily - ежедневная награда\n"
            f"/profile - профиль пользователя\n"
            f"/help - помощь\n"
            f"/site - перейти на сайт"
        )
        
        keyboard = [
            [InlineKeyboardButton("🔗 Привязать аккаунт", callback_data='link_account'),
             InlineKeyboardButton("🎁 Ежедневная награда", callback_data='daily_reward')],
            [InlineKeyboardButton("💰 Баланс", callback_data='check_balance'),
             InlineKeyboardButton("👤 Профиль", callback_data='profile')],
            [InlineKeyboardButton("🌐 Сайт itired", url=SERVER_URL)]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            welcome_text,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=reply_markup
        )
    
    async def link_account(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Привязка аккаунта"""
        query = update.callback_query
        if query:
            await query.answer()
            user = query.from_user
            message = query.message
        else:
            user = update.effective_user
            message = update.message
        
        # Проверяем, не привязан ли уже аккаунт
        try:
            response = requests.get(f'{SERVER_URL}/api/telegram/check_link', timeout=5)
            if response.status_code == 200:
                data = response.json()
                if data.get('linked'):
                    await message.reply_text(
                        f"✅ *Аккаунт уже привязан!*\n\n"
                        f"Telegram: @{data.get('telegram_username', 'пользователь')}\n\n"
                        f"Используйте команды:\n"
                        f"/balance - проверить баланс\n"
                        f"/daily - ежедневная награда\n"
                        f"/profile - профиль",
                        parse_mode=ParseMode.MARKDOWN
                    )
                    return
        except:
            pass
        
        # Генерируем код
        code = self.generate_code(8)
        expires_at = datetime.utcnow() + timedelta(minutes=15)
        
        # Сохраняем код
        self.active_codes[user.id] = {
            'code': code,
            'expires_at': expires_at,
            'username': user.username,
            'first_name': user.first_name
        }
        
        instructions = (
            f"🔑 *Код для привязки:* `{code}`\n\n"
            f"*Как привязать аккаунт:*\n"
            f"1. Перейдите на сайт {SERVER_URL}\n"
            f"2. Войдите в свой аккаунт (или зарегистрируйтесь)\n"
            f"3. В настройках профиля найдите раздел 'Telegram'\n"
            f"4. Введите этот код\n\n"
            f"⚠️ *Код действует 15 минут*\n"
            f"🔄 Для получения нового кода используйте /code"
        )
        
        keyboard = [
            [InlineKeyboardButton("🌐 Перейти на сайт", url=SERVER_URL)],
            [InlineKeyboardButton("🔄 Получить новый код", callback_data='new_code')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        if query:
            await query.edit_message_text(
                instructions,
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=reply_markup
            )
        else:
            await message.reply_text(
                instructions,
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=reply_markup
            )
    
    async def generate_code_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /code для генерации кода регистрации"""
        user = update.effective_user
        
        # Генерируем код
        code = self.generate_code(6)
        expires_at = datetime.utcnow() + timedelta(minutes=10)
        
        # Сохраняем код
        self.active_codes[user.id] = {
            'code': code,
            'expires_at': expires_at,
            'username': user.username,
            'first_name': user.first_name,
            'purpose': 'registration'
        }
        
        registration_instructions = (
            f"📝 *Код для регистрации:* `{code}`\n\n"
            f"*Как зарегистрироваться:*\n"
            f"1. Перейдите на {SERVER_URL}/register\n"
            f"2. Выберите 'Регистрация через Telegram'\n"
            f"3. Введите этот код\n"
            f"4. Заполните остальные данные\n\n"
            f"🎁 *Бонус:* За регистрацию через Telegram вы получите 200 монет!\n\n"
            f"⚠️ *Код действует 10 минут*\n"
            f"🔗 Уже есть аккаунт? Используйте /link для привязки"
        )
        
        keyboard = [
            [InlineKeyboardButton("🌐 Зарегистрироваться", url=f"{SERVER_URL}/register")],
            [InlineKeyboardButton("🔗 Привязать аккаунт", callback_data='link_account')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            registration_instructions,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=reply_markup
        )
    
    async def handle_code_input(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка ввода кода с сервера"""
        user = update.effective_user
        code = update.message.text.strip().upper()
        
        # Проверяем код
        for telegram_id, code_data in list(self.active_codes.items()):
            if code_data['code'] == code and code_data['expires_at'] > datetime.utcnow():
                # Отправляем данные на сервер
                try:
                    payload = {
                        'telegram_id': user.id,
                        'telegram_username': user.username,
                        'first_name': user.first_name,
                        'code': code,
                        'purpose': code_data.get('purpose', 'link')
                    }
                    
                    if code_data.get('purpose') == 'registration':
                        endpoint = f'{SERVER_URL}/api/telegram/register_code'
                    else:
                        endpoint = f'{SERVER_URL}/api/telegram/verify_code'
                    
                    response = requests.post(endpoint, json=payload, timeout=10)
                    
                    if response.status_code == 200:
                        data = response.json()
                        if data.get('success'):
                            # Удаляем использованный код
                            del self.active_codes[telegram_id]
                            
                            if code_data.get('purpose') == 'registration':
                                await update.message.reply_text(
                                    f"✅ *Код принят!*\n\n"
                                    f"Теперь перейдите на сайт и завершите регистрацию.\n"
                                    f"Не забудьте ввести код: `{code}`\n\n"
                                    f"После регистрации используйте /link для привязки аккаунта.",
                                    parse_mode=ParseMode.MARKDOWN
                                )
                            else:
                                await update.message.reply_text(
                                    f"✅ *Аккаунт успешно привязан!*\n\n"
                                    f"Добро пожаловать в itired, {user.first_name}!\n\n"
                                    f"Теперь вы можете:\n"
                                    f"• Получать уведомления\n"
                                    f"• Использовать все команды бота\n"
                                    f"• Получать бонусы через бота\n\n"
                                    f"Используйте /help для списка команд",
                                    parse_mode=ParseMode.MARKDOWN
                                )
                            return
                except Exception as e:
                    logger.error(f"Error verifying code: {e}")
        
        await update.message.reply_text(
            "❌ *Неверный или просроченный код*\n\n"
            "Получите новый код с помощью команд:\n"
            "/code - для регистрации\n"
            "/link - для привязки аккаунта",
            parse_mode=ParseMode.MARKDOWN
        )
    
    async def check_balance(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Проверка баланса"""
        user = update.effective_user
        
        try:
            # Получаем информацию о пользователе
            response = requests.post(
                f'{SERVER_URL}/api/telegram/get_user',
                json={'telegram_id': user.id},
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                if data.get('success'):
                    user_data = data.get('user', {})
                    balance = user_data.get('balance', 0)
                    
                    await update.message.reply_text(
                        f"💰 *Ваш баланс:* {balance} монет\n\n"
                        f"👤 Пользователь: {user_data.get('username', 'Неизвестно')}\n"
                        f"💎 Всего заработано: {user_data.get('total_earned', 0)} монет\n"
                        f"🛍️ Всего потрачено: {user_data.get('total_spent', 0)} монет\n\n"
                        f"🎵 Слушайте музыку на сайте, чтобы зарабатывать больше!",
                        parse_mode=ParseMode.MARKDOWN
                    )
                    return
        except Exception as e:
            logger.error(f"Error checking balance: {e}")
        
        await update.message.reply_text(
            "❌ *Не удалось получить информацию*\n\n"
            "Возможно, ваш аккаунт не привязан.\n"
            "Используйте /link для привязки аккаунта.",
            parse_mode=ParseMode.MARKDOWN
        )
    
    async def daily_reward(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Ежедневная награда"""
        user = update.effective_user
        
        try:
            response = requests.post(
                f'{SERVER_URL}/api/telegram/daily_reward',
                json={'telegram_id': user.id},
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                if data.get('success'):
                    reward = data.get('reward', 0)
                    balance = data.get('balance', 0)
                    consecutive_days = data.get('consecutive_days', 1)
                    
                    await update.message.reply_text(
                        f"🎁 *Ежедневная награда получена!*\n\n"
                        f"💰 +{reward} монет\n"
                        f"📈 Серия: {consecutive_days} дней подряд\n"
                        f"💵 Текущий баланс: {balance} монет\n\n"
                        f"Возвращайся завтра за новой наградой!",
                        parse_mode=ParseMode.MARKDOWN
                    )
                else:
                    await update.message.reply_text(
                        f"❌ {data.get('message', 'Ошибка получения награды')}",
                        parse_mode=ParseMode.MARKDOWN
                    )
                return
        except Exception as e:
            logger.error(f"Error getting daily reward: {e}")
        
        await update.message.reply_text(
            "❌ *Не удалось получить награду*\n\n"
            "Возможно, ваш аккаунт не привязан или возникла ошибка сервера.",
            parse_mode=ParseMode.MARKDOWN
        )
    
    async def user_profile(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Профиль пользователя"""
        user = update.effective_user
        
        try:
            response = requests.post(
                f'{SERVER_URL}/api/telegram/get_user',
                json={'telegram_id': user.id},
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                if data.get('success'):
                    user_data = data.get('user', {})
                    stats = data.get('stats', {})
                    
                    profile_text = (
                        f"👤 *Профиль пользователя*\n\n"
                        f"📛 Имя: {user_data.get('username', 'Неизвестно')}\n"
                        f"📧 Email: {user_data.get('email', 'Не указан')}\n"
                        f"💰 Баланс: {user_data.get('balance', 0)} монет\n\n"
                        f"📊 *Статистика:*\n"
                        f"🎵 Прослушано треков: {stats.get('tracks_listened', 0)}\n"
                        f"🛍️ Куплено товаров: {stats.get('items_purchased', 0)}\n"
                        f"🏆 Уровень: {stats.get('level', 1)}\n\n"
                        f"🌐 Сайт: {SERVER_URL}"
                    )
                    
                    await update.message.reply_text(
                        profile_text,
                        parse_mode=ParseMode.MARKDOWN
                    )
                    return
        except Exception as e:
            logger.error(f"Error getting profile: {e}")
        
        await update.message.reply_text(
            "❌ *Не удалось получить профиль*\n\n"
            "Возможно, ваш аккаунт не привязан.\n"
            "Используйте /link для привязки аккаунта.",
            parse_mode=ParseMode.MARKDOWN
        )
    
    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда помощи"""
        help_text = (
            "📚 *Помощь по командам itired бота*\n\n"
            "*Основные команды:*\n"
            "🔗 /link - привязать аккаунт Telegram к itired\n"
            "🔑 /code - получить код для регистрации\n"
            "💰 /balance - проверить баланс монет\n"
            "🎁 /daily - получить ежедневную награду\n"
            "👤 /profile - профиль пользователя\n"
            "🌐 /site - перейти на сайт itired\n"
            "❓ /help - эта справка\n\n"
            "*Привязка аккаунта:*\n"
            "1. Используйте /link для получения кода\n"
            "2. Перейдите на сайт itired\n"
            "3. Войдите в свой аккаунт\n"
            "4. В настройках профиля найдите раздел 'Telegram'\n"
            "5. Введите полученный код\n\n"
            "*Регистрация через Telegram:*\n"
            "1. Используйте /code для получения кода регистрации\n"
            "2. Перейдите на сайт itired и нажмите 'Регистрация через Telegram'\n"
            "3. Введите полученный код\n"
            "4. Заполните остальные данные\n"
            "5. Получите бонус 200 монет!\n\n"
            "*Поддержка:*\n"
            "По вопросам работы бота обращайтесь в поддержку на сайте."
        )
        
        await update.message.reply_text(
            help_text,
            parse_mode=ParseMode.MARKDOWN
        )
    
    async def site_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Переход на сайт"""
        keyboard = [
            [InlineKeyboardButton("🌐 Перейти на сайт itired", url=SERVER_URL)],
            [InlineKeyboardButton("📝 Регистрация", url=f"{SERVER_URL}/register")],
            [InlineKeyboardButton("🔑 Вход", url=f"{SERVER_URL}/login")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            "🌐 *Ссылки на сайт itired:*\n\n"
            f"Основной сайт: {SERVER_URL}\n"
            f"Регистрация: {SERVER_URL}/register\n"
            f"Вход: {SERVER_URL}/login\n\n"
            "Нажмите кнопку ниже для перехода:",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=reply_markup,
            disable_web_page_preview=True
        )
    
    async def handle_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка callback-запросов"""
        query = update.callback_query
        await query.answer()
        
        if query.data == 'link_account':
            await self.link_account(update, context)
        elif query.data == 'daily_reward':
            await self.daily_reward(update, context)
        elif query.data == 'check_balance':
            await self.check_balance(update, context)
        elif query.data == 'profile':
            await self.user_profile(update, context)
        elif query.data == 'new_code':
            await self.link_account(update, context)
    
    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка текстовых сообщений"""
        text = update.message.text
        
        # Если сообщение состоит из 6-8 символов (буквы и цифры), пробуем его как код
        if text and 6 <= len(text) <= 8 and all(c.isalnum() for c in text):
            await self.handle_code_input(update, context)
        else:
            await update.message.reply_text(
                "🤖 Я музыкальный бот itired!\n\n"
                "Используйте команды:\n"
                "/start - начать работу\n"
                "/link - привязать аккаунт\n"
                "/code - получить код для регистрации\n"
                "/balance - проверить баланс\n"
                "/daily - ежедневная награда\n"
                "/profile - профиль\n"
                "/help - помощь\n"
                "/site - перейти на сайт\n\n"
                "🎵 Слушайте музыку на itired!",
                parse_mode=ParseMode.MARKDOWN
            )
    
    def run(self):
        """Запуск бота"""
        if not self.token:
            logger.warning("Telegram bot token not set")
            return
        
        try:
            # Создаем приложение
            self.bot_app = Application.builder().token(self.token).build()
            
            # Добавляем обработчики
            self.bot_app.add_handler(CommandHandler('start', self.start))
            self.bot_app.add_handler(CommandHandler('link', self.link_account))
            self.bot_app.add_handler(CommandHandler('code', self.generate_code_command))
            self.bot_app.add_handler(CommandHandler('balance', self.check_balance))
            self.bot_app.add_handler(CommandHandler('daily', self.daily_reward))
            self.bot_app.add_handler(CommandHandler('profile', self.user_profile))
            self.bot_app.add_handler(CommandHandler('help', self.help_command))
            self.bot_app.add_handler(CommandHandler('site', self.site_command))
            
            # Callback handlers
            self.bot_app.add_handler(CallbackQueryHandler(self.handle_callback))
            
            # Обработчик текстовых сообщений
            self.bot_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message))
            
            # Запускаем бота
            logger.info("Starting Telegram bot...")
            self.bot_app.run_polling(
                allowed_updates=Update.ALL_TYPES,
                drop_pending_updates=True
            )
            
        except Exception as e:
            logger.error(f"Failed to start Telegram bot: {e}")

# Глобальный экземпляр бота
telegram_bot = None
bot_thread = None

def init_telegram_bot(token=None):
    """Инициализация Telegram бота"""
    global telegram_bot, bot_thread
    
    if not token:
        token = os.getenv('TELEGRAM_BOT_TOKEN')
    
    if token:
        telegram_bot = TelegramBot(token)
        
        # Запускаем бота в отдельном потоке
        def run_bot():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                telegram_bot.run()
            except Exception as e:
                logger.error(f"Bot crashed: {e}")
        
        bot_thread = threading.Thread(target=run_bot, daemon=True)
        bot_thread.start()
        logger.info(f"Telegram bot initialized with token: {token[:10]}...")
    else:
        logger.warning("TELEGRAM_BOT_TOKEN not set, bot disabled")
    
    return telegram_bot

def stop_telegram_bot():
    """Остановка Telegram бота"""
    global telegram_bot, bot_thread
    
    if telegram_bot and telegram_bot.bot_app:
        telegram_bot.bot_app.stop()
        telegram_bot = None
    
    if bot_thread:
        bot_thread.join(timeout=5)
        bot_thread = None
    
    logger.info("Telegram bot stopped")

def send_telegram_message(chat_id, text):
    """Отправка сообщения через Telegram бота"""
    if not BOT_TOKEN:
        return False
    
    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        payload = {
            'chat_id': chat_id,
            'text': text,
            'parse_mode': 'Markdown',
            'disable_web_page_preview': True
        }
        
        response = requests.post(url, json=payload, timeout=10)
        return response.status_code == 200
    except Exception as e:
        logger.error(f"Telegram send error: {e}")
        return False

if __name__ == '__main__':
    # Запуск бота отдельно
    token = os.getenv('TELEGRAM_BOT_TOKEN')
    if token:
        bot = TelegramBot(token)
        bot.run()
    else:
        print("Токен не указан. Установите переменную окружения TELEGRAM_BOT_TOKEN")