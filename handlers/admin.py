import logging
import re
import asyncio
from datetime import datetime
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from sqlalchemy import func

from config import ADMIN_IDS
from database.db import db
from database.models import User, UserRole, AdminLog, Transaction, Application
from keyboards import (
    get_admin_keyboard, 
    get_back_keyboard, 
    get_main_keyboard, 
    get_moderation_keyboard, 
    get_withdraw_keyboard
)

logger = logging.getLogger(__name__)
router = Router()

class BroadcastState(StatesGroup):
    waiting_for_broadcast = State()

class AddBalanceState(StatesGroup):
    waiting_for_user_id = State()
    waiting_for_amount = State()

class AddBalanceToUserState(StatesGroup):
    waiting_for_amount = State()

class PaymentState(StatesGroup):
    waiting_for_user_id = State()
    waiting_for_amount = State()
    waiting_for_description = State()

@router.message(F.text == "⚙️ Админ-панель")
async def admin_panel(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        await message.answer("⛔ У вас нет доступа к админ-панели")
        return
    
    await message.answer(
        "⚙️ **Админ-панель**\n\nВыберите действие:",
        parse_mode="Markdown",
        reply_markup=get_admin_keyboard()
    )

@router.message(F.text == "📋 Модерация")
async def moderation_list(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        return
    
    session = db.get_session()
    try:
        pending_applications = session.query(Application).filter(Application.status == "pending").all()
        
        if not pending_applications:
            await message.answer("📭 Нет заявок на модерацию")
            return
        
        text = "📋 Заявки на модерацию\n\n"
        for app in pending_applications[:10]:
            user = session.query(User).filter(User.id == app.user_id).first()
            if user:
                text += f"└ @{user.username or user.telegram_id}\n"
                text += f"  ID: {user.id}\n"
                if app.answers:
                    first_answer = str(app.answers[0])[:50]
                    text += f"  Ответ: {first_answer}...\n"
                text += "\n"
        
        await message.answer(text, parse_mode=None)
        
        if pending_applications:
            first_app = pending_applications[0]
            user = session.query(User).filter(User.id == first_app.user_id).first()
            if user:
                from config import QUESTIONS
                admin_text = f"📋 Заявка #{first_app.id}\n\n"
                admin_text += f"👤 Пользователь: @{user.username}\n"
                admin_text += f"🆔 ID: {user.telegram_id}\n"
                admin_text += f"📝 Ник админки: {user.admin_nick}\n"
                admin_text += f"🔑 Пароль: {user.admin_password_hash}\n\n"
                admin_text += f"Ответы:\n"
                
                if first_app.answers:
                    for i, answer in enumerate(first_app.answers, 1):
                        from config import QUESTIONS
                        admin_text += f"\n{i}. {QUESTIONS[i-1]}\n   → {answer}\n"
                
                await message.answer(admin_text, parse_mode=None, reply_markup=get_moderation_keyboard(user.id))
    finally:
        session.close()

@router.message(F.text == "📨 Рассылка")
async def broadcast_menu(message: Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS:
        return
    
    await message.answer(
        "📨 **Рассылка**\n\nВведите сообщение для рассылки всем пользователям:\n\nДля отмены нажмите 🔙 Главное меню",
        parse_mode="Markdown",
        reply_markup=get_back_keyboard()
    )
    await state.set_state(BroadcastState.waiting_for_broadcast)

@router.message(BroadcastState.waiting_for_broadcast)
async def process_broadcast(message: Message, state: FSMContext, bot: Bot):
    if message.from_user.id not in ADMIN_IDS:
        return
    
    if message.text == "🔙 Главное меню":
        await state.clear()
        await message.answer("❌ Рассылка отменена", reply_markup=get_admin_keyboard())
        return
    
    session = db.get_session()
    try:
        users = session.query(User).filter(User.telegram_id.isnot(None)).all()
        
        sent = 0
        failed = 0
        
        await message.answer(f"📨 Начинаю рассылку {len(users)} пользователям...")
        
        for user in users:
            try:
                await bot.send_message(
                    user.telegram_id,
                    f"📢 **Массовое уведомление**\n\n{message.text}",
                    parse_mode="Markdown"
                )
                sent += 1
            except Exception as e:
                failed += 1
                logger.error(f"Failed to send to {user.telegram_id}: {e}")
        
        await message.answer(
            f"✅ **Рассылка завершена!**\n\n"
            f"📨 Отправлено: {sent}\n"
            f"❌ Не доставлено: {failed}\n"
            f"📊 Всего пользователей: {len(users)}",
            parse_mode="Markdown",
            reply_markup=get_admin_keyboard()
        )
        
    except Exception as e:
        logger.error(f"Broadcast error: {e}")
        await message.answer(f"❌ Ошибка при рассылке: {e}")
    finally:
        session.close()
    
    await state.clear()

@router.message(F.text == "👥 Пользователи")
async def users_list(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        return
    
    session = db.get_session()
    try:
        all_users = session.query(User).all()
        
        if not all_users:
            await message.answer("📭 Нет пользователей")
            return
        
        pending_count = session.query(User).filter(User.role == UserRole.PENDING).count()
        user_count = session.query(User).filter(User.role == UserRole.USER).count()
        admin_count = session.query(User).filter(User.role == UserRole.ADMIN).count()
        moderator_count = session.query(User).filter(User.role == UserRole.MODERATOR).count()
        banned_count = session.query(User).filter(User.role == UserRole.BANNED).count()
        
        stats_text = f"👥 **СПИСОК ПОЛЬЗОВАТЕЛЕЙ**\n\n"
        stats_text += f"📊 **Статистика:**\n"
        stats_text += f"├ Всего: {len(all_users)}\n"
        stats_text += f"├ В ожидании: {pending_count}\n"
        stats_text += f"├ Активные: {user_count}\n"
        stats_text += f"├ Админы: {admin_count}\n"
        stats_text += f"├ Модераторы: {moderator_count}\n"
        stats_text += f"└ Заблокированы: {banned_count}\n\n"
        
        stats_text += f"📋 **Выберите пользователя:**\n"
        
        await message.answer(stats_text, parse_mode="Markdown")
        
        for user in all_users:
            status_emoji = {
                UserRole.USER: "👤",
                UserRole.ADMIN: "👑",
                UserRole.MODERATOR: "🛡️",
                UserRole.PENDING: "⏳",
                UserRole.BANNED: "🔨"
            }.get(user.role, "❓")
            
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(
                    text=f"{status_emoji} @{user.username or user.telegram_id} (ID: {user.telegram_id})",
                    callback_data=f"select_user_{user.id}"
                )]
            ])
            
            await message.answer(
                f"➖" * 20,
                reply_markup=keyboard
            )
        
    except Exception as e:
        logger.error(f"Error in users_list: {e}")
        await message.answer(f"❌ Ошибка: {e}")
    finally:
        session.close()

@router.callback_query(F.data.startswith("select_user_"))
async def select_user(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("⛔ Нет прав!", show_alert=True)
        return
    
    user_id = int(callback.data.split("_")[2])
    
    session = db.get_session()
    try:
        user = session.query(User).filter(User.id == user_id).first()
        
        if not user:
            await callback.answer("❌ Пользователь не найден")
            return
        
        status_emoji = {
            UserRole.USER: "👤",
            UserRole.ADMIN: "👑",
            UserRole.MODERATOR: "🛡️",
            UserRole.PENDING: "⏳",
            UserRole.BANNED: "🔨"
        }.get(user.role, "❓")
        
        days_in_team = (datetime.now() - user.date_joined).days if user.date_joined else 0
        
        info_text = f"{status_emoji} **@{user.username or user.telegram_id}**\n"
        info_text += f"└ 🆔 ID: `{user.telegram_id}`\n"
        info_text += f"└ 📌 Роль: {user.role.value}\n"
        info_text += f"└ 💰 Баланс: {user.total_profit:,.0f} ₽\n"
        info_text += f"└ 📅 В команде: {days_in_team} дней\n"
        info_text += f"└ 👛 Кошелек: {user.wallet_address or '❌ Не установлен'}\n\n"
        info_text += f"**👇 Выберите действие:**"
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="👤 Просмотр", callback_data=f"view_user_{user.id}"),
                InlineKeyboardButton(text="💰 Начислить", callback_data=f"add_balance_{user.id}")
            ],
            [
                InlineKeyboardButton(text="👑 Сделать админом", callback_data=f"make_admin_{user.id}"),
                InlineKeyboardButton(text="🛡️ Сделать модератором", callback_data=f"make_moderator_{user.id}")
            ],
            [
                InlineKeyboardButton(text="🔨 Заблокировать", callback_data=f"ban_{user.id}"),
                InlineKeyboardButton(text="🔓 Разблокировать", callback_data=f"unban_{user.id}")
            ],
            [InlineKeyboardButton(text="🔙 Назад к списку", callback_data="back_to_users")]
        ])
        
        await callback.message.answer(info_text, parse_mode="Markdown", reply_markup=keyboard)
        await callback.answer()
        
    finally:
        session.close()

@router.callback_query(F.data == "back_to_users")
async def back_to_users(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("⛔ Нет прав!", show_alert=True)
        return
    
    session = db.get_session()
    try:
        all_users = session.query(User).all()
        
        if not all_users:
            await callback.message.answer("📭 Нет пользователей")
            await callback.answer()
            return
        
        stats_text = f"👥 **СПИСОК ПОЛЬЗОВАТЕЛЕЙ**\n\n"
        stats_text += f"📋 **Выберите пользователя:**\n"
        
        await callback.message.answer(stats_text, parse_mode="Markdown")
        
        for user in all_users:
            status_emoji = {
                UserRole.USER: "👤",
                UserRole.ADMIN: "👑",
                UserRole.MODERATOR: "🛡️",
                UserRole.PENDING: "⏳",
                UserRole.BANNED: "🔨"
            }.get(user.role, "❓")
            
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(
                    text=f"{status_emoji} @{user.username or user.telegram_id} (ID: {user.telegram_id})",
                    callback_data=f"select_user_{user.id}"
                )]
            ])
            
            await callback.message.answer(
                f"➖" * 20,
                reply_markup=keyboard
            )
        
        await callback.answer()
        
    finally:
        session.close()

@router.message(F.text == "📊 Статистика")
async def stats(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        return
    
    session = db.get_session()
    try:
        total_users = session.query(User).count()
        pending_users = session.query(User).filter(User.role == UserRole.PENDING).count()
        active_users = session.query(User).filter(User.role == UserRole.USER).count()
        admin_users = session.query(User).filter(User.role == UserRole.ADMIN).count()
        moderator_users = session.query(User).filter(User.role == UserRole.MODERATOR).count()
        banned_users = session.query(User).filter(User.role == UserRole.BANNED).count()
        
        total_withdrawals_all = session.query(Transaction).count()
        pending_withdrawals = session.query(Transaction).filter(Transaction.status == "pending").count()
        completed_withdrawals = session.query(Transaction).filter(Transaction.status == "completed").count()
        rejected_withdrawals = session.query(Transaction).filter(Transaction.status == "rejected").count()
        
        total_amount_completed = session.query(Transaction).filter(Transaction.status == "completed").with_entities(func.sum(Transaction.amount)).scalar() or 0
        total_amount_pending = session.query(Transaction).filter(Transaction.status == "pending").with_entities(func.sum(Transaction.amount)).scalar() or 0
        
        admins = session.query(User).filter(User.role == UserRole.ADMIN).all()
        admin_list = "\n".join([f"├ @{a.username or a.telegram_id}" for a in admins]) if admins else "├ Нет"
        
        stats_text = f"""📊 **СТАТИСТИКА БОТА**

━━━━━━━━━━━━━━━━━━━━━
👥 **ПОЛЬЗОВАТЕЛИ**
├ Всего: {total_users}
├ В ожидании: {pending_users}
├ Активные: {active_users}
├ Администраторы: {admin_users}
├ Модераторы: {moderator_users}
└ Заблокировано: {banned_users}

━━━━━━━━━━━━━━━━━━━━━
👑 **АДМИНИСТРАТОРЫ**
{admin_list}

━━━━━━━━━━━━━━━━━━━━━
💰 **ВЫПЛАТЫ**
├ Всего заявок: {total_withdrawals_all}
├ В обработке: {pending_withdrawals}
├ Выполнено: {completed_withdrawals}
├ Отказано: {rejected_withdrawals}
├ Сумма выплачено: {total_amount_completed:,.0f} ₽
└ Ожидает выплаты: {total_amount_pending:,.0f} ₽
"""
        await message.answer(stats_text, parse_mode="Markdown")
    finally:
        session.close()

@router.message(F.text == "💰 Выплаты")
async def admin_withdrawals(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        return
    
    session = db.get_session()
    try:
        pending_withdrawals = session.query(Transaction).filter(Transaction.status == "pending").all()
        
        if not pending_withdrawals:
            await message.answer("📭 Нет заявок на вывод")
            return
        
        for w in pending_withdrawals:
            user = session.query(User).filter(User.id == w.user_id).first()
            if user:
                withdraw_text = f"💰 **Заявка #{w.id}**\n"
                withdraw_text += f"👤 Пользователь: @{user.username}\n"
                withdraw_text += f"🆔 ID: {user.telegram_id}\n"
                withdraw_text += f"💰 Сумма: {w.amount:,.0f} ₽\n"
                withdraw_text += f"💳 Кошелек: `{w.wallet}`\n"
                withdraw_text += f"⏰ Создана: {w.created_at.strftime('%d.%m.%Y %H:%M')}"
                await message.answer(withdraw_text, parse_mode="Markdown", reply_markup=get_withdraw_keyboard(w.id))
                
    finally:
        session.close()

@router.message(F.text == "💵 Управление балансом")
async def balance_management(message: Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS:
        return
    
    await message.answer(
        "💰 **Управление балансом**\n\nВведите Telegram ID пользователя для начисления:\n\nДля отмены нажмите 🔙 Главное меню",
        parse_mode="Markdown",
        reply_markup=get_back_keyboard()
    )
    await state.set_state(AddBalanceState.waiting_for_user_id)

@router.message(AddBalanceState.waiting_for_user_id)
async def get_user_for_balance(message: Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS:
        return
    
    if message.text == "🔙 Главное меню":
        await state.clear()
        await message.answer("❌ Отменено", reply_markup=get_admin_keyboard())
        return
    
    try:
        user_id = int(message.text.strip())
        
        session = db.get_session()
        user = session.query(User).filter(User.telegram_id == user_id).first()
        
        if not user:
            await message.answer("❌ Пользователь не найден. Попробуйте снова:")
            return
        
        await state.update_data(target_user_id=user_id, target_username=user.username)
        await state.set_state(AddBalanceState.waiting_for_amount)
        
        await message.answer(
            f"👤 **Пользователь найден:** @{user.username or user_id}\n"
            f"💰 **Текущий баланс:** {user.total_profit:,.0f} ₽\n\n"
            f"Введите сумму для начисления (в рублях):",
            parse_mode="Markdown",
            reply_markup=get_back_keyboard()
        )
    except ValueError:
        await message.answer("❌ Неверный формат ID. Введите число:")
    finally:
        session.close()

@router.message(AddBalanceState.waiting_for_amount)
async def add_balance(message: Message, state: FSMContext, bot: Bot):
    if message.from_user.id not in ADMIN_IDS:
        return
    
    if message.text == "🔙 Главное меню":
        await state.clear()
        await message.answer("❌ Отменено", reply_markup=get_admin_keyboard())
        return
    
    try:
        amount = float(message.text.strip())
        
        if amount <= 0:
            await message.answer("❌ Сумма должна быть больше 0")
            return
        
        data = await state.get_data()
        user_id = data.get('target_user_id')
        username = data.get('target_username')
        
        session = db.get_session()
        try:
            user = session.query(User).filter(User.telegram_id == user_id).first()
            
            if user:
                old_balance = user.total_profit
                user.total_profit += amount
                user.daily_profit += amount
                session.commit()
                
                admin_log = AdminLog(
                    admin_id=message.from_user.id,
                    action="add_balance",
                    target_user_id=user.id,
                    details={"amount": amount, "old_balance": old_balance, "new_balance": user.total_profit}
                )
                session.add(admin_log)
                session.commit()
                
                await message.answer(
                    f"✅ **Баланс обновлен!**\n\n"
                    f"👤 Пользователь: @{username}\n"
                    f"💰 Было: {old_balance:,.0f} ₽\n"
                    f"➕ Начислено: +{amount:,.0f} ₽\n"
                    f"💰 Стало: {user.total_profit:,.0f} ₽",
                    parse_mode="Markdown",
                    reply_markup=get_admin_keyboard()
                )
                
                await bot.send_message(
                    user_id,
                    f"💰 **Начисление средств!**\n\n"
                    f"Вам начислено: +{amount:,.0f} ₽\n"
                    f"💰 Текущий баланс: {user.total_profit:,.0f} ₽\n\n"
                    f"Для вывода средств используйте 👤 Профиль → 💰 Запрос вывода",
                    parse_mode="Markdown"
                )
                
        finally:
            session.close()
            
    except ValueError:
        await message.answer("❌ Введите корректную сумму (число):")
        return
    
    await state.clear()

@router.message(F.text == "💳 Создать оплату")
async def create_payment(message: Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS:
        await message.answer("⛔ Нет доступа")
        return
    
    await message.answer(
        "💳 **Создание оплаты**\n\n"
        "Введите Telegram ID пользователя для начисления:\n\n"
        "Для отмены нажмите 🔙 Главное меню",
        parse_mode="Markdown",
        reply_markup=get_back_keyboard()
    )
    await state.set_state(PaymentState.waiting_for_user_id)

@router.message(PaymentState.waiting_for_user_id)
async def get_payment_user(message: Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS:
        return
    
    if message.text == "🔙 Главное меню":
        await state.clear()
        await message.answer("❌ Отменено", reply_markup=get_admin_keyboard())
        return
    
    try:
        user_id = int(message.text.strip())
        
        session = db.get_session()
        user = session.query(User).filter(User.telegram_id == user_id).first()
        
        if not user:
            await message.answer("❌ Пользователь не найден. Попробуйте снова:")
            return
        
        await state.update_data(target_user_id=user_id, target_username=user.username)
        await state.set_state(PaymentState.waiting_for_amount)
        
        await message.answer(
            f"👤 **Пользователь:** @{user.username or user_id}\n"
            f"💰 **Текущий баланс:** {user.total_profit:,.0f} ₽\n\n"
            f"Введите сумму для начисления:",
            parse_mode="Markdown",
            reply_markup=get_back_keyboard()
        )
    except ValueError:
        await message.answer("❌ Неверный формат ID")
    finally:
        session.close()

@router.message(PaymentState.waiting_for_amount)
async def get_payment_amount(message: Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS:
        return
    
    if message.text == "🔙 Главное меню":
        await state.clear()
        await message.answer("❌ Отменено", reply_markup=get_admin_keyboard())
        return
    
    try:
        amount = float(message.text.strip())
        
        if amount <= 0:
            await message.answer("❌ Сумма должна быть больше 0")
            return
        
        await state.update_data(amount=amount)
        await state.set_state(PaymentState.waiting_for_description)
        
        await message.answer(
            f"💰 **Сумма:** {amount:,.0f} ₽\n\n"
            f"Введите описание оплаты (необязательно):\n\n"
            f"Для пропуска введите -",
            parse_mode="Markdown",
            reply_markup=get_back_keyboard()
        )
        
    except ValueError:
        await message.answer("❌ Введите корректную сумму")

@router.message(PaymentState.waiting_for_description)
async def process_payment(message: Message, state: FSMContext, bot: Bot):
    if message.from_user.id not in ADMIN_IDS:
        return
    
    if message.text == "🔙 Главное меню":
        await state.clear()
        await message.answer("❌ Отменено", reply_markup=get_admin_keyboard())
        return
    
    description = None if message.text == "-" else message.text
    
    data = await state.get_data()
    user_id = data.get('target_user_id')
    username = data.get('target_username')
    amount = data.get('amount')
    
    session = db.get_session()
    try:
        user = session.query(User).filter(User.telegram_id == user_id).first()
        
        if user:
            old_balance = user.total_profit
            user.total_profit += amount
            user.daily_profit += amount
            session.commit()
            
            transaction = Transaction(
                user_id=user.id,
                amount=amount,
                wallet=user.wallet_address,
                status="completed",
                description=description,
                completed_at=datetime.now()
            )
            session.add(transaction)
            session.commit()
            
            await message.answer(
                f"✅ **Оплата создана!**\n\n"
                f"👤 Пользователь: @{username}\n"
                f"💰 Сумма: {amount:,.0f} ₽\n"
                f"📝 Описание: {description or '—'}\n"
                f"💰 Баланс: {user.total_profit:,.0f} ₽",
                parse_mode="Markdown",
                reply_markup=get_admin_keyboard()
            )
            
            pay_text = f"✅ **Оплата поступила!**\n\n"
            pay_text += f"💰 Сумма: +{amount:,.0f} ₽\n"
            if description:
                pay_text += f"📝 Описание: {description}\n"
            pay_text += f"\n💎 Текущий баланс: {user.total_profit:,.0f} ₽"
            
            await bot.send_message(user_id, pay_text, parse_mode="Markdown")
            
    finally:
        session.close()
    
    await state.clear()

# ============ УПРАВЛЕНИЕ ПОЛЬЗОВАТЕЛЯМИ (INLINE) ============

@router.callback_query(F.data.startswith("view_user_"))
async def view_user_details(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("⛔ Нет прав!", show_alert=True)
        return
    
    user_id = int(callback.data.split("_")[2])
    
    session = db.get_session()
    try:
        user = session.query(User).filter(User.id == user_id).first()
        
        if not user:
            await callback.answer("❌ Пользователь не найден")
            return
        
        days_in_team = (datetime.now() - user.date_joined).days if user.date_joined else 0
        
        text = f"👤 **Детали пользователя**\n\n"
        text += f"📌 **Основное**\n"
        text += f"├ ID: `{user.telegram_id}`\n"
        text += f"├ Username: @{user.username or '—'}\n"
        text += f"├ Имя: {user.first_name or '—'}\n"
        text += f"├ Роль: {user.role.value}\n"
        text += f"└ В команде: {days_in_team} дней\n\n"
        
        text += f"🔑 **Админка**\n"
        text += f"├ Ник: {user.admin_nick or '—'}\n"
        text += f"└ Пароль: `{user.admin_password_hash or '—'}`\n\n"
        
        text += f"💰 **Финансы**\n"
        text += f"├ Баланс: {user.total_profit:,.0f} ₽\n"
        text += f"├ За день: {user.daily_profit:,.0f} ₽\n"
        text += f"└ Ставка: {user.commission_rate}%\n\n"
        
        text += f"💳 **Вывод**\n"
        text += f"└ Кошелек: {user.wallet_address or '❌ Не установлен'}"
        
        await callback.message.answer(text, parse_mode="Markdown")
        await callback.answer()
        
    finally:
        session.close()

@router.callback_query(F.data.startswith("add_balance_"))
async def add_balance_to_user(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("⛔ Нет прав!", show_alert=True)
        return
    
    user_id = int(callback.data.split("_")[2])
    
    session = db.get_session()
    try:
        user = session.query(User).filter(User.id == user_id).first()
        
        if not user:
            await callback.answer("❌ Пользователь не найден")
            return
        
        await state.update_data(target_user_id=user.telegram_id, target_username=user.username)
        await state.set_state(AddBalanceToUserState.waiting_for_amount)
        
        await callback.message.answer(
            f"👤 **Пользователь:** @{user.username or user.telegram_id}\n"
            f"💰 **Текущий баланс:** {user.total_profit:,.0f} ₽\n\n"
            f"Введите сумму для начисления (в рублях):\n\n"
            f"Для отмены нажмите 🔙 Главное меню",
            parse_mode="Markdown",
            reply_markup=get_back_keyboard()
        )
        await callback.answer()
        
    finally:
        session.close()

@router.message(AddBalanceToUserState.waiting_for_amount)
async def process_add_balance_to_user(message: Message, state: FSMContext, bot: Bot):
    if message.from_user.id not in ADMIN_IDS:
        return
    
    if message.text == "🔙 Главное меню":
        await state.clear()
        await message.answer("❌ Отменено", reply_markup=get_admin_keyboard())
        return
    
    try:
        amount = float(message.text.strip())
        
        if amount <= 0:
            await message.answer("❌ Сумма должна быть больше 0")
            return
        
        data = await state.get_data()
        user_id = data.get('target_user_id')
        username = data.get('target_username')
        
        session = db.get_session()
        try:
            user = session.query(User).filter(User.telegram_id == user_id).first()
            
            if user:
                old_balance = user.total_profit
                user.total_profit += amount
                user.daily_profit += amount
                session.commit()
                
                admin_log = AdminLog(
                    admin_id=message.from_user.id,
                    action="add_balance",
                    target_user_id=user.id,
                    details={"amount": amount, "old_balance": old_balance, "new_balance": user.total_profit}
                )
                session.add(admin_log)
                session.commit()
                
                await message.answer(
                    f"✅ **Баланс обновлен!**\n\n"
                    f"👤 Пользователь: @{username}\n"
                    f"💰 Было: {old_balance:,.0f} ₽\n"
                    f"➕ Начислено: +{amount:,.0f} ₽\n"
                    f"💰 Стало: {user.total_profit:,.0f} ₽",
                    parse_mode="Markdown",
                    reply_markup=get_admin_keyboard()
                )
                
                await bot.send_message(
                    user_id,
                    f"💰 **Начисление средств!**\n\n"
                    f"Вам начислено: +{amount:,.0f} ₽\n"
                    f"💰 Текущий баланс: {user.total_profit:,.0f} ₽\n\n"
                    f"Для вывода средств используйте 👤 Профиль → 💰 Запрос вывода",
                    parse_mode="Markdown"
                )
                
        finally:
            session.close()
            
    except ValueError:
        await message.answer("❌ Введите корректную сумму (число):")
        return
    
    await state.clear()

@router.callback_query(F.data.startswith("make_admin_"))
async def make_admin(callback: CallbackQuery, bot: Bot):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("⛔ Нет прав!", show_alert=True)
        return
    
    user_id = int(callback.data.split("_")[2])
    
    session = db.get_session()
    try:
        user = session.query(User).filter(User.id == user_id).first()
        if user:
            user.role = UserRole.ADMIN
            session.commit()
            
            await callback.answer("✅ Пользователь назначен администратором!")
            
            await bot.send_message(
                user.telegram_id,
                "👑 **Вы назначены администратором!**\n\n"
                "Теперь вам доступна админ-панель.",
                parse_mode="Markdown"
            )
    finally:
        session.close()

@router.callback_query(F.data.startswith("make_moderator_"))
async def make_moderator(callback: CallbackQuery, bot: Bot):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("⛔ Нет прав!", show_alert=True)
        return
    
    user_id = int(callback.data.split("_")[2])
    
    session = db.get_session()
    try:
        user = session.query(User).filter(User.id == user_id).first()
        if user:
            user.role = UserRole.MODERATOR
            session.commit()
            
            await callback.answer("✅ Пользователь назначен модератором!")
            
            await bot.send_message(
                user.telegram_id,
                "🛡️ **Вы назначены модератором!**\n\n"
                "Теперь вы можете модерировать заявки.",
                parse_mode="Markdown"
            )
    finally:
        session.close()

@router.callback_query(F.data.startswith("ban_"))
async def ban_user(callback: CallbackQuery, bot: Bot):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("⛔ Нет прав!", show_alert=True)
        return
    
    user_id = int(callback.data.split("_")[2])
    
    session = db.get_session()
    try:
        user = session.query(User).filter(User.id == user_id).first()
        if user:
            user.role = UserRole.BANNED
            session.commit()
            
            await callback.answer("🔨 Пользователь заблокирован!")
            
            await bot.send_message(
                user.telegram_id,
                "🔨 **Ваш аккаунт заблокирован!**\n\n"
                "Обратитесь к администратору для разблокировки.",
                parse_mode="Markdown"
            )
    finally:
        session.close()

@router.callback_query(F.data.startswith("unban_"))
async def unban_user(callback: CallbackQuery, bot: Bot):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("⛔ Нет прав!", show_alert=True)
        return
    
    user_id = int(callback.data.split("_")[2])
    
    session = db.get_session()
    try:
        user = session.query(User).filter(User.id == user_id).first()
        if user:
            user.role = UserRole.USER
            session.commit()
            
            await callback.answer("✅ Пользователь разблокирован!")
            
            await bot.send_message(
                user.telegram_id,
                "✅ **Ваш аккаунт разблокирован!**\n\n"
                "Теперь вам снова доступны все функции.",
                parse_mode="Markdown"
            )
    finally:
        session.close()

@router.callback_query(F.data.startswith("pay_"))
async def process_payment(callback: CallbackQuery, bot: Bot):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("⛔ Нет прав!", show_alert=True)
        return
    
    withdraw_id = int(callback.data.split("_")[1])
    
    session = db.get_session()
    try:
        withdraw = session.query(Transaction).filter(Transaction.id == withdraw_id).first()
        
        if not withdraw or withdraw.status != "pending":
            await callback.answer("❌ Заявка уже обработана!", show_alert=True)
            return
        
        user = session.query(User).filter(User.id == withdraw.user_id).first()
        
        if not user:
            await callback.answer("❌ Пользователь не найден!", show_alert=True)
            return
        
        if user.total_profit < withdraw.amount:
            await callback.answer("❌ Недостаточно средств на балансе!", show_alert=True)
            return
        
        user.total_profit -= withdraw.amount
        user.daily_profit -= withdraw.amount
        withdraw.status = "completed"
        withdraw.completed_at = datetime.now()
        session.commit()
        
        await bot.send_message(
            user.telegram_id,
            f"✅ **Выплата выполнена!**\n\n"
            f"Сумма: {withdraw.amount:,.0f} ₽\n"
            f"Кошелек: {withdraw.wallet}\n\n"
            f"💰 Остаток на балансе: {user.total_profit:,.0f} ₽",
            parse_mode="Markdown"
        )
        
        await callback.message.edit_text(
            callback.message.text + "\n\n✅ **ВЫПЛАЧЕНО!**",
            parse_mode="Markdown",
            reply_markup=None
        )
        await callback.answer("✅ Выплата выполнена!")
        
    except Exception as e:
        logger.error(f"Error in process_payment: {e}")
        session.rollback()
        await callback.answer(f"❌ Ошибка: {e}")
    finally:
        session.close()

@router.callback_query(F.data.startswith("reject_pay_"))
async def reject_payment(callback: CallbackQuery, bot: Bot):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("⛔ Нет прав!", show_alert=True)
        return
    
    withdraw_id = int(callback.data.split("_")[2])
    
    session = db.get_session()
    try:
        withdraw = session.query(Transaction).filter(Transaction.id == withdraw_id).first()
        
        if not withdraw or withdraw.status != "pending":
            await callback.answer("❌ Заявка уже обработана!", show_alert=True)
            return
        
        withdraw.status = "rejected"
        session.commit()
        
        user = session.query(User).filter(User.id == withdraw.user_id).first()
        
        if user:
            await bot.send_message(
                user.telegram_id,
                f"❌ **Выплата отклонена!**\n\n"
                f"Сумма: {withdraw.amount:,.0f} ₽\n\n"
                f"💰 Средства остались на балансе.\n"
                f"Свяжитесь с администратором для уточнения.",
                parse_mode="Markdown"
            )
        
        await callback.message.edit_text(
            callback.message.text + "\n\n❌ **ОТКАЗАНО!**",
            parse_mode="Markdown",
            reply_markup=None
        )
        await callback.answer("❌ Выплата отклонена!")
        
    except Exception as e:
        logger.error(f"Error in reject_payment: {e}")
        session.rollback()
        await callback.answer(f"❌ Ошибка: {e}")
    finally:
        session.close()

# ============ ГЛАВНОЕ МЕНЮ - ВОЗВРАТ ============

@router.message(F.text == "🔙 Главное меню")
async def back_to_main_admin(message: Message):
    if message.from_user.id in ADMIN_IDS:
        await message.answer("✅ Главное меню", parse_mode="Markdown", reply_markup=get_main_keyboard("admin"))
    else:
        session = db.get_session()
        try:
            user = session.query(User).filter(User.telegram_id == message.from_user.id).first()
            if user:
                await message.answer("✅ Главное меню", parse_mode="Markdown", reply_markup=get_main_keyboard(user.role.value))
            else:
                await message.answer("✅ Главное меню", parse_mode="Markdown", reply_markup=get_main_keyboard("user"))
        finally:
            session.close()