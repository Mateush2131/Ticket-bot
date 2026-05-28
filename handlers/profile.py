import logging
import hashlib
from datetime import datetime
from aiogram import Router, F, Bot
from aiogram.types import Message
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from config import ADMIN_IDS, SUPPORT_IDS
from database.db import db
from database.models import User, Transaction, Referral
from keyboards import get_main_keyboard, get_profile_keyboard, get_back_keyboard, get_withdraw_keyboard, get_support_keyboard, get_info_keyboard, get_payments_keyboard

logger = logging.getLogger(__name__)
router = Router()

class WalletState(StatesGroup):
    waiting_for_wallet = State()

class WithdrawState(StatesGroup):
    waiting_for_amount = State()

class SupportState(StatesGroup):
    waiting_for_admin_message = State()
    waiting_for_support_message = State()

@router.message(F.text == "👤 Профиль")
async def show_profile(message: Message):
    session = db.get_session()
    try:
        if message.from_user.id in ADMIN_IDS:
            user = session.query(User).filter(User.telegram_id == message.from_user.id).first()
            
            if user:
                days_in_team = (datetime.now() - user.date_joined).days if user.date_joined else 0
                
                profile_text = f"""👑 **Профиль администратора**

━━━━━━━━━━━━━━━━━━━━━
📌 **Основная информация**
├ Роль: {user.role.value}
├ В команде: {days_in_team} дней
└ Дата вступления: {user.date_joined.strftime('%d.%m.%Y') if user.date_joined else '—'}

━━━━━━━━━━━━━━━━━━━━━
🔑 **Доступ к админке**
├ Ник: `{user.admin_nick or '—'}`
└ Пароль: `••••••••••••`

━━━━━━━━━━━━━━━━━━━━━
💰 **Финансы**
├ Общий профит: {user.total_profit:,.0f} ₽
├ Профит за день: {user.daily_profit:,.0f} ₽
└ Ставка: {user.commission_rate}%

━━━━━━━━━━━━━━━━━━━━━
💳 **Вывод средств**
├ Кошелек: {user.wallet_address or '❌ Не установлен'}
└ Доступно к выводу: {user.total_profit:,.0f} ₽
"""
                await message.answer(profile_text, parse_mode=None, reply_markup=get_profile_keyboard())
            else:
                await message.answer(
                    "👑 **Профиль администратора**\n\n"
                    "Вы не зарегистрированы как пользователь, но имеете полный доступ к админ-панели.\n\n"
                    "Для получения пользовательских функций, зарегистрируйтесь как обычный пользователь.",
                    parse_mode=None,
                    reply_markup=get_profile_keyboard()
                )
            return
        
        user = session.query(User).filter(User.telegram_id == message.from_user.id).first()
        
        if not user:
            await message.answer("❌ Пользователь не найден")
            return
        
        days_in_team = (datetime.now() - user.date_joined).days if user.date_joined else 0
        
        profile_text = f"""👤 **Мой профиль**

━━━━━━━━━━━━━━━━━━━━━
📌 **Основная информация**
├ Роль: {user.role.value}
├ В команде: {days_in_team} дней
└ Дата вступления: {user.date_joined.strftime('%d.%m.%Y') if user.date_joined else '—'}

━━━━━━━━━━━━━━━━━━━━━
🔑 **Доступ к админке**
├ Ник: `{user.admin_nick or '—'}`
└ Пароль: `••••••••••••`

━━━━━━━━━━━━━━━━━━━━━
💰 **Финансы**
├ Общий профит: {user.total_profit:,.0f} ₽
├ Профит за день: {user.daily_profit:,.0f} ₽
└ Ставка: {user.commission_rate}%

━━━━━━━━━━━━━━━━━━━━━
💳 **Вывод средств**
├ Кошелек: {user.wallet_address or '❌ Не установлен'}
└ Доступно к выводу: {user.total_profit:,.0f} ₽

━━━━━━━━━━━━━━━━━━━━━
🔗 **Реферальная система**
├ Переходов: {user.referrals[0].clicks if user.referrals else 0}
└ Регистраций: {user.referrals[0].registrations if user.referrals else 0}
"""
        
        await message.answer(profile_text, parse_mode=None, reply_markup=get_profile_keyboard())
    finally:
        session.close()

@router.message(F.text == "💳 Установить кошелек")
async def set_wallet(message: Message, state: FSMContext):
    await message.answer(
        "💳 **Введите адрес кошелька для выплат:**\n\n"
        "Поддерживаются:\n"
        "• USDT (TRC20)\n"
        "• Bitcoin\n"
        "• Ethereum\n\n"
        "Введите адрес:",
        parse_mode=None,
        reply_markup=get_back_keyboard()
    )
    await state.set_state(WalletState.waiting_for_wallet)

@router.message(WalletState.waiting_for_wallet)
async def process_wallet(message: Message, state: FSMContext):
    if message.text == "🔙 Главное меню":
        await state.clear()
        user = db.get_session().query(User).filter(User.telegram_id == message.from_user.id).first()
        await message.answer("❌ Отменено", reply_markup=get_main_keyboard(user.role.value if user else "user"))
        return
    
    wallet = message.text.strip()
    
    session = db.get_session()
    try:
        user = session.query(User).filter(User.telegram_id == message.from_user.id).first()
        if user:
            user.wallet_address = wallet
            session.commit()
            await message.answer("✅ **Кошелек успешно установлен!**", parse_mode=None, reply_markup=get_profile_keyboard())
    finally:
        session.close()
    
    await state.clear()

@router.message(F.text == "🔐 Показать пароль")
async def show_password(message: Message):
    session = db.get_session()
    try:
        user = session.query(User).filter(User.telegram_id == message.from_user.id).first()
        if user and user.admin_password_hash:
            await message.answer(
                f"🔑 **Ваш пароль от админ-панели:**\n`{user.admin_password_hash}`\n\n⚠️ Никому не передавайте этот пароль!",
                parse_mode=None
            )
        else:
            await message.answer("❌ Пароль не найден")
    finally:
        session.close()

@router.message(F.text == "💰 Запрос вывода")
async def request_withdraw(message: Message, state: FSMContext):
    session = db.get_session()
    try:
        user = session.query(User).filter(User.telegram_id == message.from_user.id).first()
        
        if not user:
            await message.answer("❌ Пользователь не найден")
            return
        
        if not user.wallet_address:
            await message.answer("❌ Сначала установите кошелек в профиле!")
            return
        
        if user.total_profit < 100:
            await message.answer("❌ Минимальная сумма вывода: 100 ₽")
            return
        
        await message.answer(
            f"💰 **Запрос на вывод средств**\n\n"
            f"Доступно к выводу: {user.total_profit:,.0f} ₽\n"
            f"Кошелек: {user.wallet_address}\n\n"
            f"Введите сумму для вывода (мин. 100 ₽):",
            parse_mode=None,
            reply_markup=get_back_keyboard()
        )
        await state.set_state(WithdrawState.waiting_for_amount)
    finally:
        session.close()

@router.message(WithdrawState.waiting_for_amount)
async def process_withdraw(message: Message, state: FSMContext, bot: Bot):
    if message.text == "🔙 Главное меню":
        await state.clear()
        user = db.get_session().query(User).filter(User.telegram_id == message.from_user.id).first()
        await message.answer("❌ Отменено", reply_markup=get_main_keyboard(user.role.value if user else "user"))
        return
    
    try:
        amount = float(message.text)
        
        if amount < 100:
            await message.answer("❌ Минимальная сумма вывода: 100 ₽", reply_markup=get_back_keyboard())
            return
        
        session = db.get_session()
        try:
            user = session.query(User).filter(User.telegram_id == message.from_user.id).first()
            
            if amount > user.total_profit:
                await message.answer(f"❌ Недостаточно средств. Доступно: {user.total_profit:,.0f} ₽", reply_markup=get_back_keyboard())
                return
            
            withdraw = Transaction(
                user_id=user.id,
                amount=amount,
                wallet=user.wallet_address,
                status="pending"
            )
            session.add(withdraw)
            session.commit()
            
            await message.answer(
                f"✅ **Заявка на вывод {amount:,.0f} ₽ отправлена!**\n\n"
                f"Средства будут переведены на кошелек:\n`{user.wallet_address}`\n\n"
                f"Ожидайте обработки (до 24 часов).",
                parse_mode=None,
                reply_markup=get_main_keyboard(user.role.value)
            )
            
            for admin_id in ADMIN_IDS:
                try:
                    await bot.send_message(
                        admin_id,
                        f"💰 **Заявка на вывод!**\n\n"
                        f"👤 Пользователь: @{user.username}\n"
                        f"💰 Сумма: {amount:,.0f} ₽\n"
                        f"💳 Кошелек: {user.wallet_address}",
                        parse_mode=None,
                        reply_markup=get_withdraw_keyboard(withdraw.id)
                    )
                except:
                    pass
            
        finally:
            session.close()
    except ValueError:
        await message.answer("❌ Введите корректную сумму", reply_markup=get_back_keyboard())
        return
    
    await state.clear()

@router.message(F.text == "📊 Моя статистика")
async def show_stats(message: Message):
    session = db.get_session()
    try:
        user = session.query(User).filter(User.telegram_id == message.from_user.id).first()
        
        if user:
            stats_text = f"""📊 **Ваша статистика**

━━━━━━━━━━━━━━━━━━━━━
💰 **Финансы**
├ Общий профит: {user.total_profit:,.0f} ₽
├ Профит за день: {user.daily_profit:,.0f} ₽
└ Ставка: {user.commission_rate}%

━━━━━━━━━━━━━━━━━━━━━
📈 **Активность**
├ В команде: {(datetime.now() - user.date_joined).days if user.date_joined else 0} дней
├ Рефералов: {user.referrals[0].registrations if user.referrals else 0}
└ Уровень: {user.role.value}

━━━━━━━━━━━━━━━━━━━━━
💳 **Выводы**
├ Кошелек: {user.wallet_address or '❌ Не установлен'}
└ Доступно: {user.total_profit:,.0f} ₽
"""
            await message.answer(stats_text, parse_mode=None)
    finally:
        session.close()

@router.message(F.text == "🔗 Реферальная ссылка")
async def get_referral_link(message: Message):
    session = db.get_session()
    try:
        user = session.query(User).filter(User.telegram_id == message.from_user.id).first()
        
        if not user:
            await message.answer("❌ Пользователь не найден")
            return
        
        from config import BOT_TOKEN
        bot_username = "Ticketappl_bot"
        
        referral_link = f"https://t.me/{bot_username}?start={user.referral_link}"
        
        text = f"🔗 **Ваша реферальная ссылка**\n\n"
        text += f"`{referral_link}`\n\n"
        text += f"📊 **Статистика:**\n"
        if user.referrals:
            text += f"├ Переходов: {user.referrals[0].clicks}\n"
            text += f"└ Регистраций: {user.referrals[0].registrations}\n\n"
        else:
            text += f"├ Переходов: 0\n"
            text += f"└ Регистраций: 0\n\n"
        text += f"💰 За каждого приглашенного вы получаете **50 ₽** на баланс!"
        
        await message.answer(text, parse_mode=None)
        
    finally:
        session.close()

@router.message(F.text == "💰 Выплаты")
async def payments_menu(message: Message):
    await message.answer(
        "💰 **Меню выплат**\n\n"
        "Выберите действие:",
        parse_mode=None,
        reply_markup=get_payments_keyboard()
    )

@router.message(F.text == "💳 Мои кошельки")
async def my_wallets(message: Message):
    session = db.get_session()
    try:
        user = session.query(User).filter(User.telegram_id == message.from_user.id).first()
        
        if not user:
            await message.answer("❌ Пользователь не найден")
            return
        
        if user.wallet_address:
            await message.answer(
                f"💳 **Мои кошельки**\n\n"
                f"💰 Основной кошелек:\n"
                f"`{user.wallet_address}`\n\n"
                f"Для изменения кошелька используйте 👤 Профиль → 💳 Установить кошелек",
                parse_mode=None
            )
        else:
            await message.answer(
                "💳 **Мои кошельки**\n\n"
                "❌ Кошелек не установлен.\n\n"
                "Установите кошелек в 👤 Профиль → 💳 Установить кошелек",
                parse_mode=None
            )
    finally:
        session.close()

@router.message(F.text == "💰 Запросить выплату")
async def request_withdraw_from_menu(message: Message, state: FSMContext):
    await request_withdraw(message, state)

@router.message(F.text == "📋 История выплат")
async def withdraw_history(message: Message):
    session = db.get_session()
    try:
        user = session.query(User).filter(User.telegram_id == message.from_user.id).first()
        
        if not user:
            await message.answer("❌ Пользователь не найден")
            return
        
        withdrawals = session.query(Transaction).filter(Transaction.user_id == user.id).order_by(Transaction.created_at.desc()).limit(10).all()
        
        if not withdrawals:
            await message.answer(
                "📋 **История выплат**\n\n"
                "У вас пока нет запросов на вывод средств.\n\n"
                "Чтобы запросить вывод, нажмите 💰 Запросить выплату",
                parse_mode=None
            )
            return
        
        history_text = "📋 **История выплат**\n\n"
        
        for w in withdrawals:
            status_emoji = {
                "pending": "⏳",
                "completed": "✅",
                "rejected": "❌"
            }.get(w.status, "❓")
            
            status_text = {
                "pending": "Ожидает",
                "completed": "Выплачено",
                "rejected": "Отказано"
            }.get(w.status, "Неизвестно")
            
            history_text += f"{status_emoji} **{w.amount:,.0f} ₽**\n"
            history_text += f"└ {w.created_at.strftime('%d.%m.%Y %H:%M')} - {status_text}\n"
            if w.completed_at and w.status == "completed":
                history_text += f"└ Выплачено: {w.completed_at.strftime('%d.%m.%Y %H:%M')}\n"
            history_text += "\n"
        
        await message.answer(history_text, parse_mode=None)
        
    except Exception as e:
        logger.error(f"Error in withdraw_history: {e}")
        await message.answer("❌ Ошибка при получении истории выплат")
    finally:
        session.close()

@router.message(F.text == "📚 Информация")
async def info_menu(message: Message):
    await message.answer(
        "📚 **Информация**\n\n"
        "Выберите раздел:",
        parse_mode=None,
        reply_markup=get_info_keyboard()
    )

@router.message(F.text == "🛟 Поддержка")
async def support_menu(message: Message):
    await message.answer(
        "🛟 **Поддержка**\n\n"
        "Выберите кому написать:",
        parse_mode=None,
        reply_markup=get_support_keyboard()
    )

@router.message(F.text == "📝 Написать администратору")
async def write_to_admin(message: Message, state: FSMContext):
    await message.answer(
        "📝 **Напишите ваше сообщение администратору:**\n\n"
        "Мы ответим в ближайшее время.",
        parse_mode=None,
        reply_markup=get_back_keyboard()
    )
    await state.set_state(SupportState.waiting_for_admin_message)

@router.message(F.text == "💬 Написать саппорту")
async def write_to_support(message: Message, state: FSMContext):
    await message.answer(
        "💬 **Напишите ваше сообщение саппорту:**\n\n"
        "Мы ответим в ближайшее время.",
        parse_mode=None,
        reply_markup=get_back_keyboard()
    )
    await state.set_state(SupportState.waiting_for_support_message)

@router.message(SupportState.waiting_for_admin_message)
async def forward_to_admin(message: Message, state: FSMContext, bot: Bot):
    if message.text == "🔙 Главное меню":
        await state.clear()
        user = db.get_session().query(User).filter(User.telegram_id == message.from_user.id).first()
        await message.answer("❌ Отменено", reply_markup=get_main_keyboard(user.role.value if user else "user"))
        return
    
    for admin_id in ADMIN_IDS:
        try:
            await bot.send_message(
                admin_id,
                f"📨 **Сообщение от пользователя**\n\n"
                f"👤 @{message.from_user.username}\n"
                f"🆔 ID: {message.from_user.id}\n\n"
                f"📝 {message.text}",
                parse_mode=None
            )
        except:
            pass
    
    await message.answer("✅ **Сообщение отправлено администратору!**\n\nМы ответим в ближайшее время.", parse_mode=None)
    await state.clear()
    
    user = db.get_session().query(User).filter(User.telegram_id == message.from_user.id).first()
    await message.answer("Главное меню", reply_markup=get_main_keyboard(user.role.value if user else "user"))

@router.message(SupportState.waiting_for_support_message)
async def forward_to_support(message: Message, state: FSMContext, bot: Bot):
    if message.text == "🔙 Главное меню":
        await state.clear()
        user = db.get_session().query(User).filter(User.telegram_id == message.from_user.id).first()
        await message.answer("❌ Отменено", reply_markup=get_main_keyboard(user.role.value if user else "user"))
        return
    
    sent_count = 0
    for support_id in SUPPORT_IDS:
        try:
            await bot.send_message(
                support_id,
                f"💬 **Сообщение в саппорт**\n\n"
                f"👤 От: @{message.from_user.username}\n"
                f"🆔 ID: {message.from_user.id}\n\n"
                f"📝 {message.text}",
                parse_mode=None
            )
            sent_count += 1
        except Exception as e:
            print(f"❌ Не удалось отправить саппорту {support_id}: {e}")
    
    if sent_count > 0:
        await message.answer(
            f"✅ **Сообщение отправлено саппорту!**\n\n"
            f"Мы ответим в ближайшее время.",
            parse_mode=None
        )
    else:
        await message.answer(
            "❌ **Ошибка!**\n\n"
            "Не удалось отправить сообщение. Попробуйте позже.",
            parse_mode=None
        )
    
    await state.clear()
    
    user = db.get_session().query(User).filter(User.telegram_id == message.from_user.id).first()
    await message.answer("Главное меню", reply_markup=get_main_keyboard(user.role.value if user else "user"))

@router.message(F.text == "📖 Мануалы")
async def manuals(message: Message):
    await message.answer(
        "📖 **Мануалы**\n\n"
        "1. Инструкция по работе с админ-панелью: [ссылка]\n"
        "2. Инструкция по выводу средств: [ссылка]\n"
        "3. FAQ: [ссылка]\n\n"
        "По всем вопросам обращайтесь в поддержку.",
        parse_mode=None
    )

@router.message(F.text == "💬 Чаты")
async def chats(message: Message):
    await message.answer(
        "💬 **Наши чаты**\n\n"
        "• Общий чат: [ссылка]\n"
        "• Новостной канал: [ссылка]\n"
        "• Чат для обсуждений: [ссылка]",
        parse_mode=None
    )

@router.message(F.text == "📜 Правила")
async def rules(message: Message):
    await message.answer(
        "📜 **Правила проекта**\n\n"
        "1. Уважайте других участников\n"
        "2. Запрещен спам и флуд\n"
        "3. Запрещена передача паролей третьим лицам\n"
        "4. Вывод средств осуществляется в течение 24 часов\n"
        "5. За нарушение правил - блокировка аккаунта\n\n"
        "Нарушение правил влечет за собой блокировку!",
        parse_mode=None
    )

@router.message(F.text == "🔙 Главное меню")
async def back_to_main(message: Message):
    session = db.get_session()
    try:
        if message.from_user.id in ADMIN_IDS:
            await message.answer("✅ Главное меню", parse_mode=None, reply_markup=get_main_keyboard("admin"))
        else:
            user = session.query(User).filter(User.telegram_id == message.from_user.id).first()
            if user:
                await message.answer("✅ Главное меню", parse_mode=None, reply_markup=get_main_keyboard(user.role.value))
            else:
                await message.answer("✅ Главное меню", parse_mode=None, reply_markup=get_main_keyboard("user"))
    finally:
        session.close()