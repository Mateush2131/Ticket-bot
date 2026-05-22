import logging
from datetime import datetime
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from sqlalchemy import func

from config import MODERATOR_IDS, ADMIN_IDS
from database.db import db
from database.models import User, UserRole, Application, Transaction
from keyboards import get_moderator_keyboard, get_main_keyboard

logger = logging.getLogger(__name__)
router = Router()

# Состояния для назначения админа
class AdminAssign(StatesGroup):
    waiting_for_id = State()

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

# ========== НОВЫЙ ХЭНДЛЕР: Назначение админа ==========

@router.message(F.text == "👑 Назначить админа")
async def assign_admin_start(message: Message, state: FSMContext):
    if not is_moderator(message.from_user.id):
        await message.answer("⛔ Нет прав")
        return
    
    await message.answer(
        "👑 **Назначение администратора**\n\n"
        "Отправьте **Telegram ID** пользователя, которому хотите дать права администратора.\n\n"
        "📌 *Где взять ID?*\n"
        "• В профиле пользователя есть кнопка «Копировать ID»\n"
        "• Или используйте бота @userinfobot\n\n"
        "❗️ Отправьте только число (ID):",
        parse_mode="Markdown"
    )
    await state.set_state(AdminAssign.waiting_for_id)

@router.message(AdminAssign.waiting_for_id)
async def assign_admin_process(message: Message, state: FSMContext, bot: Bot):
    if not is_moderator(message.from_user.id):
        await state.clear()
        return
    
    # Проверяем, что введено число
    try:
        target_id = int(message.text.strip())
    except ValueError:
        await message.answer("❌ **Ошибка!**\n\nВведите корректный Telegram ID (только цифры).\n\nПример: `123456789`", parse_mode="Markdown")
        return
    
    session = db.get_session()
    try:
        # Ищем пользователя в БД
        user = session.query(User).filter(User.telegram_id == target_id).first()
        
        if not user:
            await message.answer(
                f"❌ **Пользователь с ID `{target_id}` не найден**\n\n"
                f"Возможные причины:\n"
                f"• Пользователь еще не запускал бота\n"
                f"• Неверный ID\n\n"
                f"Попробуйте снова или отмените команду.",
                parse_mode="Markdown"
            )
            return
        
        # Проверяем, не админ ли уже
        if user.role == UserRole.ADMIN:
            await message.answer(
                f"⚠️ **Пользователь `@{user.username}` уже является администратором!**\n\n"
                f"Действие отменено.",
                parse_mode="Markdown"
            )
            return
        
        # Сохраняем старую роль для отчета
        old_role = user.role.value
        
        # Назначаем админа
        user.role = UserRole.ADMIN
        session.commit()
        
        # Уведомляем всех админов
        for admin_id in ADMIN_IDS:
            try:
                await bot.send_message(
                    admin_id,
                    f"👑 **НАЗНАЧЕН НОВЫЙ АДМИНИСТРАТОР!**\n\n"
                    f"━━━━━━━━━━━━━━━━━━━━━\n"
                    f"👤 **Назначил:** @{message.from_user.username} (модератор)\n"
                    f"👤 **Новый админ:** @{user.username}\n"
                    f"🆔 **ID:** `{user.telegram_id}`\n"
                    f"📋 **Была роль:** {old_role}\n"
                    f"━━━━━━━━━━━━━━━━━━━━━",
                    parse_mode="Markdown"
                )
            except Exception as e:
                logger.error(f"Не удалось уведомить админа {admin_id}: {e}")
        
        # Подтверждение модератору
        await message.answer(
            f"✅ **Пользователь назначен администратором!**\n\n"
            f"━━━━━━━━━━━━━━━━━━━━━\n"
            f"👤 **Пользователь:** @{user.username}\n"
            f"🆔 **ID:** `{user.telegram_id}`\n"
            f"📋 **Старая роль:** {old_role}\n"
            f"👑 **Новая роль:** Администратор\n"
            f"━━━━━━━━━━━━━━━━━━━━━",
            parse_mode="Markdown"
        )
        
        # Сообщаем пользователю о назначении
        try:
            await bot.send_message(
                target_id,
                "👑 **Поздравляем!**\n\n"
                "Вам присвоена роль **Администратора**!\n\n"
                "Теперь вам доступны все админ-функции бота.\n\n"
                "🔹 Используйте админ-панель для управления ботом.",
                parse_mode="Markdown"
            )
        except Exception as e:
            await message.answer(
                f"⚠️ **Внимание!**\n\n"
                f"Пользователь @{user.username} назначен админом, "
                f"но бот не смог отправить ему уведомление.\n"
                f"Возможно, пользователь заблокировал бота.",
                parse_mode="Markdown"
            )
            
    except Exception as e:
        logger.error(f"Ошибка при назначении админа: {e}")
        await message.answer(f"❌ **Произошла ошибка:** `{str(e)}`", parse_mode="Markdown")
    finally:
        session.close()
    
    await state.clear()

@router.message(F.text == "◀️ Назад")
async def mod_back_to_main(message: Message):
    if not is_moderator(message.from_user.id):
        return
    
    from handlers.user import show_main_menu
    await show_main_menu(message)