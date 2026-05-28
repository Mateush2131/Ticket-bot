import logging
from datetime import datetime
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from config import ADMIN_IDS
from database.db import db
from database.models import User, Transaction
from keyboards import get_cancel_keyboard, get_admin_keyboard

logger = logging.getLogger(__name__)
router = Router()

class PaymentState(StatesGroup):
    waiting_for_user_id = State()
    waiting_for_amount = State()
    waiting_for_description = State()

@router.message(F.text == "💳 Создать оплату")
async def create_payment(message: Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS:
        await message.answer("⛔ Нет доступа")
        return
    
    await message.answer(
        "💳 **Создание оплаты**\n\n"
        "Введите Telegram ID пользователя для начисления:\n\n"
        "Для отмены нажмите ❌ Отмена",
        parse_mode=None,
        reply_markup=get_cancel_keyboard()
    )
    await state.set_state(PaymentState.waiting_for_user_id)

@router.message(PaymentState.waiting_for_user_id)
async def get_payment_user(message: Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS:
        return
    
    if message.text == "❌ Отмена":
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
            parse_mode=None,
            reply_markup=get_cancel_keyboard()
        )
    except ValueError:
        await message.answer("❌ Неверный формат ID")
    finally:
        session.close()

@router.message(PaymentState.waiting_for_amount)
async def get_payment_amount(message: Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS:
        return
    
    if message.text == "❌ Отмена":
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
            parse_mode=None,
            reply_markup=get_cancel_keyboard()
        )
        
    except ValueError:
        await message.answer("❌ Введите корректную сумму")

@router.message(PaymentState.waiting_for_description)
async def process_payment(message: Message, state: FSMContext, bot: Bot):
    if message.from_user.id not in ADMIN_IDS:
        return
    
    if message.text == "❌ Отмена":
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
                parse_mode=None,
                reply_markup=get_admin_keyboard()
            )
            
            pay_text = f"✅ **Оплата поступила!**\n\n"
            pay_text += f"💰 Сумма: +{amount:,.0f} ₽\n"
            if description:
                pay_text += f"📝 Описание: {description}\n"
            pay_text += f"\n💎 Текущий баланс: {user.total_profit:,.0f} ₽"
            
            await bot.send_message(user_id, pay_text, parse_mode=None)
            
    finally:
        session.close()
    
    await state.clear()