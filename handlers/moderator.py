import logging
from datetime import datetime
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from sqlalchemy import func

from config import MODERATOR_IDS, ADMIN_IDS
from database.db import db
from database.models import User, UserRole, Application, Transaction
from keyboards import get_moderator_keyboard, get_main_keyboard

logger = logging.getLogger(__name__)
router = Router()

def is_moderator(user_id: int) -> bool:
    return user_id in MODERATOR_IDS or user_id in ADMIN_IDS

@router.message(F.text == "🛡️ Модератор-панель")
async def moderator_panel(message: Message):
    if not is_moderator(message.from_user.id):
        await message.answer("⛔ У вас нет доступа к модератор-панели")
        return
    
    await message.answer(
        "🛡️ **Модератор-панель**\n\n"
        "Выберите действие:",
        parse_mode="Markdown",
        reply_markup=get_moderator_keyboard()
    )

@router.message(F.text == "📋 Модерация заявок")
async def moderator_moderation(message: Message):
    if not is_moderator(message.from_user.id):
        return
    
    session = db.get_session()
    try:
        pending_applications = session.query(Application).filter(Application.status == "pending").all()
        
        if not pending_applications:
            await message.answer("📭 Нет заявок на модерацию")
            return
        
        for app in pending_applications[:10]:
            user = session.query(User).filter(User.id == app.user_id).first()
            if user:
                from config import QUESTIONS
                text = f"📋 **Заявка #{app.id}**\n\n"
                text += f"👤 Пользователь: @{user.username}\n"
                text += f"🆔 ID: {user.telegram_id}\n\n"
                text += f"**Ответы:**\n"
                
                if app.answers:
                    for i, answer in enumerate(app.answers, 1):
                        text += f"\n*{i}. {QUESTIONS[i-1]}*\n   → {answer}\n"
                
                keyboard = InlineKeyboardMarkup(inline_keyboard=[
                    [
                        InlineKeyboardButton(text="✅ Принять", callback_data=f"mod_approve_{app.id}"),
                        InlineKeyboardButton(text="❌ Отклонить", callback_data=f"mod_reject_{app.id}")
                    ]
                ])
                
                await message.answer(text, parse_mode="Markdown", reply_markup=keyboard)
                
    finally:
        session.close()

@router.callback_query(F.data.startswith("mod_approve_"))
async def moderator_approve(callback: CallbackQuery, bot: Bot):
    if not is_moderator(callback.from_user.id):
        await callback.answer("⛔ Нет прав!", show_alert=True)
        return
    
    app_id = int(callback.data.split("_")[2])
    
    session = db.get_session()
    try:
        app = session.query(Application).filter(Application.id == app_id).first()
        if app and app.status == "pending":
            user = session.query(User).filter(User.id == app.user_id).first()
            if user:
                user.role = UserRole.USER
                user.date_joined = datetime.now()
                app.status = "approved"
                app.moderated_by = callback.from_user.id
                app.moderated_at = datetime.now()
                session.commit()
                
                for admin_id in ADMIN_IDS:
                    try:
                        await bot.send_message(
                            admin_id,
                            f"📢 **Модератор одобрил заявку!**\n\n"
                            f"👤 Модератор: @{callback.from_user.username}\n"
                            f"👤 Пользователь: @{user.username}\n"
                            f"🆔 ID: {user.telegram_id}",
                            parse_mode="Markdown"
                        )
                    except:
                        pass
                
                await bot.send_message(
                    user.telegram_id,
                    "🎉 **Поздравляем! Ваша заявка одобрена!**\n\n"
                    "Теперь вам доступны все функции бота.",
                    parse_mode="Markdown",
                    reply_markup=get_main_keyboard(user.role.value)
                )
                
                await callback.message.edit_text(
                    callback.message.text + "\n\n✅ **ЗАЯВКА ОДОБРЕНА!**",
                    parse_mode="Markdown"
                )
                await callback.answer("✅ Заявка одобрена!")
                
    finally:
        session.close()

@router.callback_query(F.data.startswith("mod_reject_"))
async def moderator_reject(callback: CallbackQuery, bot: Bot):
    if not is_moderator(callback.from_user.id):
        await callback.answer("⛔ Нет прав!", show_alert=True)
        return
    
    app_id = int(callback.data.split("_")[2])
    
    session = db.get_session()
    try:
        app = session.query(Application).filter(Application.id == app_id).first()
        if app and app.status == "pending":
            user = session.query(User).filter(User.id == app.user_id).first()
            if user:
                user.role = UserRole.BANNED
                app.status = "rejected"
                app.moderated_by = callback.from_user.id
                app.moderated_at = datetime.now()
                session.commit()
                
                for admin_id in ADMIN_IDS:
                    try:
                        await bot.send_message(
                            admin_id,
                            f"📢 **Модератор отклонил заявку!**\n\n"
                            f"👤 Модератор: @{callback.from_user.username}\n"
                            f"👤 Пользователь: @{user.username}\n"
                            f"🆔 ID: {user.telegram_id}",
                            parse_mode="Markdown"
                        )
                    except:
                        pass
                
                await bot.send_message(
                    user.telegram_id,
                    "❌ **К сожалению, ваша заявка отклонена.**\n\n"
                    "Вы можете подать заявку снова через 30 дней.",
                    parse_mode="Markdown"
                )
                
                await callback.message.edit_text(
                    callback.message.text + "\n\n❌ **ЗАЯВКА ОТКЛОНЕНА!**",
                    parse_mode="Markdown"
                )
                await callback.answer("❌ Заявка отклонена!")
                
    finally:
        session.close()

@router.message(F.text == "📊 Статистика")
async def moderator_stats(message: Message):
    if not is_moderator(message.from_user.id):
        return
    
    session = db.get_session()
    try:
        total_users = session.query(User).count()
        pending_users = session.query(User).filter(User.role == UserRole.PENDING).count()
        active_users = session.query(User).filter(User.role == UserRole.USER).count()
        
        total_withdrawals = session.query(Transaction).filter(Transaction.status == "completed").count()
        total_amount = session.query(Transaction).filter(Transaction.status == "completed").with_entities(func.sum(Transaction.amount)).scalar() or 0
        
        stats_text = f"""📊 **СТАТИСТИКА (Модератор)**

━━━━━━━━━━━━━━━━━━━━━
👥 **ПОЛЬЗОВАТЕЛИ**
├ Всего: {total_users}
├ В ожидании: {pending_users}
└ Активные: {active_users}

━━━━━━━━━━━━━━━━━━━━━
💰 **ВЫПЛАТЫ**
├ Всего выплат: {total_withdrawals}
└ Сумма: {total_amount:,.0f} ₽
"""
        await message.answer(stats_text, parse_mode="Markdown")
    finally:
        session.close()