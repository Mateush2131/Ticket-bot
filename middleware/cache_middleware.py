from typing import Callable, Dict, Any, Awaitable
from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery
from redis_cache import redis_cache
from database.db import db
from database.models import User

class CacheMiddleware(BaseMiddleware):
    """Middleware для кэширования пользователей"""
    
    async def __call__(
        self,
        handler: Callable[[Message, Dict[str, Any]], Awaitable[Any]],
        event: Message | CallbackQuery,
        data: Dict[str, Any]
    ) -> Any:
        user_id = event.from_user.id
        
        cached_user = redis_cache.get_user(user_id)
        
        if cached_user:
            data['cached_user'] = cached_user
        else:
            session = db.get_session()
            try:
                user = session.query(User).filter(User.telegram_id == user_id).first()
                if user:
                    user_data = {
                        'id': user.id,
                        'telegram_id': user.telegram_id,
                        'username': user.username,
                        'first_name': user.first_name,
                        'role': user.role.value,
                        'total_profit': user.total_profit,
                        'wallet_address': user.wallet_address
                    }
                    redis_cache.set_user(user_id, user_data)
                    data['cached_user'] = user_data
            finally:
                session.close()
        
        return await handler(event, data)