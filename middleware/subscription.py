import logging
from typing import Callable, Dict, Any, Awaitable
from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery
from aiogram.enums import ChatMemberStatus
from config import REQUIRED_CHANNELS
from keyboards import get_subscription_keyboard

logger = logging.getLogger(__name__)

class SubscriptionMiddleware(BaseMiddleware):
    """Middleware для проверки подписки на каналы"""
    
    async def __call__(
        self,
        handler: Callable[[Message, Dict[str, Any]], Awaitable[Any]],
        event: Message | CallbackQuery,
        data: Dict[str, Any]
    ) -> Any:
        user = event.from_user
        
        # Пропускаем админов и модераторов
        from config import ADMIN_IDS, MODERATOR_IDS
        if user.id in ADMIN_IDS or user.id in MODERATOR_IDS:
            return await handler(event, data)
        
        # Проверяем подписку на каналы
        bot = data.get("bot")
        not_subscribed = []
        
        for channel in REQUIRED_CHANNELS:
            try:
                member = await bot.get_chat_member(chat_id=channel["id"], user_id=user.id)
                if member.status in [ChatMemberStatus.LEFT, ChatMemberStatus.KICKED]:
                    not_subscribed.append(channel)
            except Exception as e:
                logger.error(f"Error checking subscription for {channel['id']}: {e}")
                not_subscribed.append(channel)
        
        if not_subscribed:
            text = "⚠️ **Для доступа к боту необходимо подписаться на следующие каналы и чаты:**\n\n"
            for channel in not_subscribed:
                text += f"🔹 [{channel['name']}]({channel['url']})\n"
            text += "\n✅ После подписки нажмите кнопку «Проверить подписку»"
            
            if isinstance(event, Message):
                await event.answer(text, parse_mode="Markdown", disable_web_page_preview=True,
                                   reply_markup=get_subscription_keyboard())
            else:
                await event.message.answer(text, parse_mode="Markdown", disable_web_page_preview=True,
                                           reply_markup=get_subscription_keyboard())
            return
        
        return await handler(event, data)