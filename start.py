#!/usr/bin/env python3
"""
Скрипт для запуска itired платформы
Запускает веб-сервер и Telegram бота одновременно
"""

import os
import sys
import subprocess
import threading
import time
from dotenv import load_dotenv

# Загружаем переменные окружения
load_dotenv()

def run_flask_server():
    """Запуск Flask сервера"""
    print("🚀 Запуск Flask сервера...")
    
    # Устанавливаем переменные окружения для Flask
    os.environ['FLASK_APP'] = 'app.py'
    os.environ['FLASK_ENV'] = 'development'
    
    # Запускаем Flask сервер
    subprocess.run([sys.executable, '-m', 'flask', 'run', '--host=0.0.0.0', '--port=5001'])

def run_telegram_bot():
    """Запуск Telegram бота"""
    print("🤖 Запуск Telegram бота...")
    
    # Ждем немного, чтобы сервер успел запуститься
    time.sleep(3)
    
    # Запускаем бота
    import telegram_bot
    telegram_token = os.getenv('TELEGRAM_BOT_TOKEN')
    
    if telegram_token:
        telegram_bot.init_telegram_bot(telegram_token)
        print("✅ Telegram бот запущен")
    else:
        print("⚠️ Telegram токен не настроен, бот не будет запущен")

def run_both():
    """Запуск сервера и бота одновременно"""
    print("🎵 Запуск itired платформы...")
    print("=" * 50)
    
    # Создаем потоки
    server_thread = threading.Thread(target=run_flask_server, daemon=True)
    bot_thread = threading.Thread(target=run_telegram_bot, daemon=True)
    
    # Запускаем потоки
    server_thread.start()
    bot_thread.start()
    
    try:
        # Держим программу активной
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n\n👋 Остановка itired платформы...")
        sys.exit(0)

if __name__ == '__main__':
    # Проверяем наличие токена Telegram бота
    if not os.getenv('TELEGRAM_BOT_TOKEN'):
        print("⚠️  Внимание: TELEGRAM_BOT_TOKEN не настроен")
        print("   Telegram бот не будет работать")
        print("   Настройте токен в файле .env")
        print()
    
    # Проверяем аргументы командной строки
    if len(sys.argv) > 1:
        if sys.argv[1] == 'server':
            run_flask_server()
        elif sys.argv[1] == 'bot':
            run_telegram_bot()
        elif sys.argv[1] == 'both':
            run_both()
        else:
            print("Использование: python start.py [server|bot|both]")
            print("  server - запустить только веб-сервер")
            print("  bot    - запустить только Telegram бота")
            print("  both   - запустить всё вместе (по умолчанию)")
    else:
        run_both()