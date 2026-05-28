import asyncio
import logging
import sys
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from config import BOT_TOKEN
from database.db import db
from handlers.start import router as start_router
from handlers.profile import router as profile_router
from handlers.admin import router as admin_router
from handlers.moderator import router as moderator_router
from middleware.subscription import SubscriptionMiddleware
from middleware.cache_middleware import CacheMiddleware
from redis_cache import redis_cache

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('bot.log', encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)

async def main():
    logger.info("🚀 Запуск бота...")
    
    try:
        db.init_db()
        logger.info("✅ MySQL база данных инициализирована")
    except Exception as e:
        logger.error(f"❌ Ошибка базы данных: {e}")
        return
    
    if redis_cache.enabled:
        logger.info("✅ Redis кэш подключен")
    else:
        logger.warning("⚠️ Redis не подключен, кэш отключен")
    
    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher(storage=MemoryStorage())
    
    dp.message.middleware(SubscriptionMiddleware())
    dp.callback_query.middleware(SubscriptionMiddleware())
    dp.message.middleware(CacheMiddleware())
    dp.callback_query.middleware(CacheMiddleware())
    
    dp.include_router(start_router)
    dp.include_router(profile_router)
    dp.include_router(admin_router)
    dp.include_router(moderator_router)
    
    logger.info("✅ Бот успешно запущен!")
    
    try:
        await dp.start_polling(bot, allowed_updates=["message", "callback_query"])
    finally:
        await bot.session.close()
        db.close()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("⏹️ Бот остановлен")