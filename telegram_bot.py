import os
import logging
import json
from datetime import datetime, timedelta
import threading
import random
import string
from typing import Optional

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
from telegram.constants import ParseMode

logger = logging.getLogger(__name__)

# Состояния для ConversationHandler
WAITING_CODE, LINK_ACCOUNT, VERIFY_ACCOUNT = range(3)

class TelegramBot:
    def __init__(self, token: str, app=None):
        self.token = token
        self.app = app
        self.bot_app = None
        self.user_sessions = {}
        
    def init_app(self, app):
        self.app = app
        return self
    
    def generate_verification_code(self, length=6):
        """Генерация кода подтверждения"""
        return ''.join(random.choices(string.digits, k=length))
    
    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /start"""
        user = update.effective_user
        
        # Импортируем модели здесь, чтобы избежать циклических импортов
        from models import db, TelegramSession
        
        # Создаем или обновляем сессию
        session = TelegramSession.query.filter_by(telegram_id=user.id).first()
        if not session:
            session = TelegramSession(
                telegram_id=user.id,
                chat_id=update.effective_chat.id,
                username=user.username,
                first_name=user.first_name,
                last_name=user.last_name,
                is_bot=user.is_bot
            )
            db.session.add(session)
        else:
            session.chat_id = update.effective_chat.id
            session.username = user.username
            session.first_name = user.first_name
            session.last_name = user.last_name
            session.last_active = datetime.utcnow()
        
        db.session.commit()
        
        # Проверяем, привязан ли аккаунт
        from models import User
        linked_user = User.query.filter_by(telegram_id=user.id).first()
        
        if linked_user:
            # Аккаунт уже привязан
            await update.message.reply_text(
                f"👋 Привет, {user.first_name}!\n"
                f"Твой аккаунт уже привязан к пользователю *{linked_user.username}*.\n\n"
                f"📊 Баланс: *{linked_user.currency.balance if linked_user.currency else 0} монет*\n"
                f"🎵 Слушано треков: *{linked_user.statistic.tracks_listened if linked_user.statistic else 0}*\n\n"
                f"Используй команды:\n"
                f"/balance - узнать баланс\n"
                f"/profile - профиль\n"
                f"/daily - ежедневная награда\n"
                f"/recommend - рекомендации\n"
                f"/unlink - отвязать аккаунт",
                parse_mode=ParseMode.MARKDOWN
            )
            return ConversationHandler.END
        else:
            # Предлагаем привязать аккаунт
            keyboard = [
                [InlineKeyboardButton("🔗 Привязать аккаунт", callback_data='link_account')],
                [InlineKeyboardButton("📝 Зарегистрироваться", callback_data='register')]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(
                f"👋 Привет, {user.first_name}!\n"
                f"Я — бот музыкальной платформы itired 🎵\n\n"
                f"Выбери действие:",
                reply_markup=reply_markup
            )
            return WAITING_CODE
    
    async def link_account(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Привязка существующего аккаунта"""
        query = update.callback_query
        await query.answer()
        
        user = update.effective_user
        code = self.generate_verification_code()
        expires = datetime.utcnow() + timedelta(minutes=10)
        
        # Сохраняем код в сессии
        from models import db, TelegramSession
        session = TelegramSession.query.filter_by(telegram_id=user.id).first()
        if session:
            session.session_data = json.dumps({
                'verification_code': code,
                'action': 'link',
                'expires': expires.isoformat()
            })
            db.session.commit()
        
        await query.edit_message_text(
            f"🔗 *Привязка аккаунта*\n\n"
            f"1. Перейди на сайт itired\n"
            f"2. Войди в свой аккаунт\n"
            f"3. Перейди в настройки профиля\n"
            f"4. Введи этот код:\n\n"
            f"`{code}`\n\n"
            f"⚠️ Код действует 10 минут\n"
            f"❌ Отмена: /cancel",
            parse_mode=ParseMode.MARKDOWN
        )
        
        return ConversationHandler.END
    
    async def register_account(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Регистрация нового аккаунта через Telegram"""
        query = update.callback_query
        await query.answer()
        
        user = update.effective_user
        code = self.generate_verification_code()
        expires = datetime.utcnow() + timedelta(minutes=10)
        
        # Генерируем временный пароль
        temp_password = ''.join(random.choices(string.ascii_letters + string.digits, k=8))
        
        # Сохраняем в сессии
        from models import db, TelegramSession
        session = TelegramSession.query.filter_by(telegram_id=user.id).first()
        if session:
            session.session_data = json.dumps({
                'verification_code': code,
                'action': 'register',
                'temp_password': temp_password,
                'telegram_data': {
                    'id': user.id,
                    'username': user.username,
                    'first_name': user.first_name,
                    'last_name': user.last_name
                },
                'expires': expires.isoformat()
            })
            db.session.commit()
        
        await query.edit_message_text(
            f"📝 *Регистрация нового аккаунта*\n\n"
            f"1. Перейди на сайт itired\n"
            f"2. Нажми 'Регистрация через Telegram'\n"
            f"3. Введи этот код:\n\n"
            f"`{code}`\n\n"
            f"📋 Твои данные для входа:\n"
            f"👤 Логин: `{user.username or str(user.id)}`\n"
            f"🔑 Пароль: `{temp_password}`\n\n"
            f"⚠️ Код действует 10 минут\n"
            f"❌ Отмена: /cancel",
            parse_mode=ParseMode.MARKDOWN
        )
        
        return ConversationHandler.END
    
    async def daily_reward(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Ежедневная награда через бота"""
        user = update.effective_user
        
        from models import User, CurrencyTransaction, db
        from datetime import datetime
        from utils import add_currency
        import random
        
        linked_user = User.query.filter_by(telegram_id=user.id).first()
        
        if not linked_user:
            await update.message.reply_text(
                "❌ Сначала привяжи свой аккаунт с помощью /start"
            )
            return
        
        # Проверяем, получал ли уже награду сегодня
        last_reward = CurrencyTransaction.query.filter_by(
            user_id=linked_user.id,
            reason='daily_reward'
        ).order_by(CurrencyTransaction.created_at.desc()).first()
        
        if last_reward and last_reward.created_at.date() == datetime.utcnow().date():
            await update.message.reply_text(
                "🎁 Ты уже получал награду сегодня!\n"
                "Возвращайся завтра 😊"
            )
            return
        
        # Выдаем награду
        reward = random.randint(10, 25)
        if add_currency(linked_user.id, reward, 'daily_reward', {'via': 'telegram'}):
            await update.message.reply_text(
                f"🎉 *Ежедневная награда получена!*\n\n"
                f"💰 +{reward} монет\n"
                f"💵 Баланс: {linked_user.currency.balance if linked_user.currency else 0}",
                parse_mode=ParseMode.MARKDOWN
            )
        else:
            await update.message.reply_text("❌ Ошибка выдачи награды")
    
    async def balance(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Проверка баланса"""
        user = update.effective_user
        
        from models import User
        linked_user = User.query.filter_by(telegram_id=user.id).first()
        
        if not linked_user:
            await update.message.reply_text(
                "❌ Сначала привяжи свой аккаунт с помощью /start"
            )
            return
        
        balance = linked_user.currency.balance if linked_user.currency else 0
        total_earned = linked_user.currency.total_earned if linked_user.currency else 0
        total_spent = linked_user.currency.total_spent if linked_user.currency else 0
        
        await update.message.reply_text(
            f"💰 *Твой баланс*\n\n"
            f"💵 Доступно: *{balance}* монет\n"
            f"📈 Всего заработано: *{total_earned}*\n"
            f"📉 Всего потрачено: *{total_spent}*\n\n"
            f"🎵 Слушай музыку на сайте, чтобы получать больше монет!",
            parse_mode=ParseMode.MARKDOWN
        )
    
    async def profile(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Профиль пользователя"""
        user = update.effective_user
        
        from models import User
        linked_user = User.query.filter_by(telegram_id=user.id).first()
        
        if not linked_user:
            await update.message.reply_text(
                "❌ Сначала привяжи свой аккаунт с помощью /start"
            )
            return
        
        stats = linked_user.statistic
        await update.message.reply_text(
            f"👤 *Профиль пользователя*\n\n"
            f"📛 Имя: *{linked_user.display_name}*\n"
            f"🎯 Уровень: *{stats.level if stats else 1}*\n"
            f"🎵 Треков прослушано: *{stats.tracks_listened if stats else 0}*\n"
            f"⏱️ Минут музыки: *{stats.minutes_listened if stats else 0}*\n"
            f"🏆 Достижений: *{stats.achievements_unlocked if stats else 0}*\n"
            f"💰 Баланс: *{linked_user.currency.balance if linked_user.currency else 0}* монет\n\n"
            f"🌐 Сайт: http://localhost:5001/profile/{linked_user.username}",
            parse_mode=ParseMode.MARKDOWN
        )
    
    async def recommendations(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Рекомендации музыки"""
        user = update.effective_user
        
        from models import User
        from utils import recommender
        
        linked_user = User.query.filter_by(telegram_id=user.id).first()
        
        if not linked_user:
            await update.message.reply_text(
                "❌ Сначала привяжи свой аккаунт с помощью /start"
            )
            return
        
        try:
            # Получаем рекомендации
            recs = recommender.get_enhanced_recommendations(
                linked_user.id, 
                linked_user.settings.music_service if linked_user.settings else 'yandex'
            )
            
            if not recs:
                await update.message.reply_text(
                    "🎵 Пока нет рекомендаций.\n"
                    "Слушай больше музыки на сайте!"
                )
                return
            
            # Отправляем первые 3 рекомендации
            message = "🎧 *Твои рекомендации на сегодня:*\n\n"
            for i, rec in enumerate(recs[:3], 1):
                message += f"{i}. *{rec['title']}*\n"
                if 'artists' in rec:
                    message += f"   👤 {', '.join(rec['artists'][:2])}\n"
                if 'source' in rec:
                    message += f"   📍 {rec['source']}\n"
                message += "\n"
            
            message += "🎯 Слушай эти треки на сайте itired!"
            await update.message.reply_text(message, parse_mode=ParseMode.MARKDOWN)
            
        except Exception as e:
            logger.error(f"Recommendations error: {e}")
            await update.message.reply_text("❌ Ошибка получения рекомендаций")
    
    async def unlink_account(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Отвязка аккаунта"""
        user = update.effective_user
        
        from models import User, db
        linked_user = User.query.filter_by(telegram_id=user.id).first()
        
        if not linked_user:
            await update.message.reply_text("❌ Аккаунт не привязан")
            return
        
        keyboard = [
            [InlineKeyboardButton("✅ Да, отвязать", callback_data='confirm_unlink')],
            [InlineKeyboardButton("❌ Нет, отмена", callback_data='cancel_unlink')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            f"⚠️ *Подтверждение отвязки*\n\n"
            f"Ты уверен, что хочешь отвязать аккаунт *{linked_user.username}*?\n\n"
            f"После отвязки:\n"
            f"• Не сможешь получать уведомления в Telegram\n"
            f"• Не будет доступа к командам бота\n"
            f"• Данные аккаунта сохранятся на сайте",
            reply_markup=reply_markup,
            parse_mode=ParseMode.MARKDOWN
        )
    
    async def confirm_unlink(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Подтверждение отвязки"""
        query = update.callback_query
        await query.answer()
        
        user = update.effective_user
        
        from models import User, db
        linked_user = User.query.filter_by(telegram_id=user.id).first()
        
        if linked_user:
            linked_user.telegram_id = None
            linked_user.telegram_verified = False
            linked_user.telegram_username = None
            db.session.commit()
        
        await query.edit_message_text(
            "✅ Аккаунт успешно отвязан!\n\n"
            "Ты всегда можешь привязать его заново через /start"
        )
    
    async def cancel_unlink(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Отмена отвязки"""
        query = update.callback_query
        await query.answer()
        await query.edit_message_text("❌ Отвязка отменена")
    
    async def cancel(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Отмена текущего действия"""
        await update.message.reply_text(
            "❌ Действие отменено\n"
            "Используй /start для начала работы"
        )
        return ConversationHandler.END
    
    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка текстовых сообщений"""
        await update.message.reply_text(
            "🤖 Я музыкальный бот itired!\n\n"
            "Доступные команды:\n"
            "/start - начать работу\n"
            "/balance - баланс монет\n"
            "/profile - профиль\n"
            "/daily - ежедневная награда\n"
            "/recommend - рекомендации\n"
            "/unlink - отвязать аккаунт\n\n"
            "🎵 Слушай музыку на itired.com"
        )
    
    def run(self):
        """Запуск бота"""
        if not self.token:
            logger.warning("Telegram bot token not set")
            return
        
        try:
            # Создаем приложение
            self.bot_app = Application.builder().token(self.token).build()
            
            # Conversation handler для регистрации/привязки
            conv_handler = ConversationHandler(
                entry_points=[CommandHandler('start', self.start)],
                states={
                    WAITING_CODE: [
                        CallbackQueryHandler(self.link_account, pattern='^link_account$'),
                        CallbackQueryHandler(self.register_account, pattern='^register$')
                    ]
                },
                fallbacks=[CommandHandler('cancel', self.cancel)]
            )
            
            # Добавляем обработчики
            self.bot_app.add_handler(conv_handler)
            self.bot_app.add_handler(CommandHandler('daily', self.daily_reward))
            self.bot_app.add_handler(CommandHandler('balance', self.balance))
            self.bot_app.add_handler(CommandHandler('profile', self.profile))
            self.bot_app.add_handler(CommandHandler('recommend', self.recommendations))
            self.bot_app.add_handler(CommandHandler('unlink', self.unlink_account))
            
            # Callback handlers
            self.bot_app.add_handler(CallbackQueryHandler(self.confirm_unlink, pattern='^confirm_unlink$'))
            self.bot_app.add_handler(CallbackQueryHandler(self.cancel_unlink, pattern='^cancel_unlink$'))
            
            # Обработчик текстовых сообщений
            self.bot_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message))
            
            # Запускаем бота
            logger.info("Starting Telegram bot...")
            self.bot_app.run_polling(allowed_updates=Update.ALL_TYPES)
            
        except Exception as e:
            logger.error(f"Failed to start Telegram bot: {e}")

# Создаем глобальный экземпляр бота
telegram_bot = None

def init_telegram_bot(token=None):
    """Инициализация Telegram бота"""
    global telegram_bot
    if not token:
        token = os.getenv('TELEGRAM_BOT_TOKEN')
    
    if token:
        telegram_bot = TelegramBot(token)
        # Запускаем бота в отдельном потоке
        thread = threading.Thread(target=telegram_bot.run, daemon=True)
        thread.start()
        logger.info(f"Telegram bot initialized with token: {token[:10]}...")
    else:
        logger.warning("TELEGRAM_BOT_TOKEN not set, bot disabled")
    
    return telegram_bot