import logging
import random
import string
import hashlib
import asyncio
from datetime import datetime
from aiogram import Router, Bot, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from config import QUESTIONS, MIN_ADMIN_NICK_LENGTH, MAX_ADMIN_NICK_LENGTH, ADMIN_IDS
from database.db import db
from database.models import User, UserRole, Application, Referral
from keyboards import get_main_keyboard, get_moderation_keyboard, get_back_keyboard
from casino_api import casino_api

logger = logging.getLogger(__name__)
router = Router()

class RegisterStates(StatesGroup):
    waiting_for_answer = State()
    waiting_for_nick = State()

def generate_password(length: int = 12) -> str:
    chars = string.ascii_letters + string.digits + "!@#$%^&*"
    return ''.join(random.choice(chars) for _ in range(length))

async def notify_admins(bot, admin_ids, text, reply_markup):
    for admin_id in admin_ids:
        try:
            await bot.send_message(admin_id, text, parse_mode=None, reply_markup=reply_markup)
        except:
            pass

@router.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext):
    if message.from_user.id in ADMIN_IDS:
        await message.answer(
            f"✅ **Добро пожаловать, Администратор!**\n\n"
            f"Вам доступна админ-панель.\n\n"
            f"👇 Используйте кнопки ниже:",
            parse_mode=None,
            reply_markup=get_main_keyboard("admin")
        )
        return
    
    session = db.get_session()
    try:
        args = message.text.split()
        referral_code = None
        if len(args) > 1:
            referral_code = args[1]
        
        user = session.query(User).filter(User.telegram_id == message.from_user.id).first()
        
        if not message.from_user.username:
            await message.answer("⚠️ Установите username в Telegram и нажмите /start")
            return
        
        if not user:
            if referral_code:
                referrer = session.query(User).filter(User.referral_link == referral_code).first()
                if referrer:
                    await state.update_data(referral_id=referrer.id)
                    referral = session.query(Referral).filter(Referral.owner_id == referrer.id).first()
                    if referral:
                        referral.clicks += 1
                        session.commit()
            
            await message.answer(
                f"👋 Добро пожаловать!\n\n"
                f"📝 **Вопрос 1 из {len(QUESTIONS)}:**\n{QUESTIONS[0]}",
                parse_mode=None
            )
            await state.update_data(answers=[], question_index=0)
            await state.set_state(RegisterStates.waiting_for_answer)
        else:
            if user.role == UserRole.PENDING:
                await message.answer("⏳ Ваша заявка на модерации. Ожидайте решения.")
            elif user.role == UserRole.BANNED:
                await message.answer("🚫 Ваш аккаунт заблокирован.")
            else:
                await message.answer(
                    f"✅ С возвращением, {message.from_user.first_name}!",
                    reply_markup=get_main_keyboard(user.role.value)
                )
    finally:
        session.close()

@router.message(RegisterStates.waiting_for_answer)
async def process_answer(message: Message, state: FSMContext):
    data = await state.get_data()
    answers = data.get('answers', [])
    index = data.get('question_index', 0)
    
    answers.append(message.text)
    
    if index + 1 < len(QUESTIONS):
        await state.update_data(answers=answers, question_index=index + 1)
        await message.answer(
            f"📝 **Вопрос {index + 2} из {len(QUESTIONS)}:**\n{QUESTIONS[index + 1]}",
            parse_mode=None
        )
    else:
        await state.update_data(answers=answers)
        await state.set_state(RegisterStates.waiting_for_nick)
        await message.answer(
            f"✅ Анкета заполнена!\n\n"
            f"Придумайте **никнейм для админ-панели**\n"
            f"Требования: от {MIN_ADMIN_NICK_LENGTH} до {MAX_ADMIN_NICK_LENGTH} символов\n"
            f"Разрешены латинские буквы, цифры и знак подчеркивания\n\n"
            f"Введите ваш ник:",
            parse_mode=None,
            reply_markup=get_back_keyboard()
        )

@router.message(RegisterStates.waiting_for_nick)
async def process_nick(message: Message, state: FSMContext, bot: Bot):
    if message.text == "🔙 Главное меню":
        await state.clear()
        await message.answer("❌ Регистрация отменена", reply_markup=get_main_keyboard("user"))
        return
    
    nick = message.text.strip()
    
    if not (MIN_ADMIN_NICK_LENGTH <= len(nick) <= MAX_ADMIN_NICK_LENGTH):
        await message.answer(
            f"❌ Ошибка!\n\n"
            f"Ник должен быть от {MIN_ADMIN_NICK_LENGTH} до {MAX_ADMIN_NICK_LENGTH} символов.\n"
            f"Сейчас: {len(nick)} символов.\n\n"
            f"Попробуйте снова:",
            reply_markup=get_back_keyboard()
        )
        return
    
    if not all(c.isalnum() or c == '_' for c in nick):
        await message.answer(
            "❌ Ошибка!\n\n"
            "Ник может содержать только:\n"
            "• Латинские буквы (a-z, A-Z)\n"
            "• Цифры (0-9)\n"
            "• Знак подчеркивания (_)\n\n"
            "Попробуйте снова:",
            reply_markup=get_back_keyboard()
        )
        return
    
    data = await state.get_data()
    answers = data.get('answers', [])
    password = generate_password()
    
    session = db.get_session()
    try:
        existing_user = session.query(User).filter(User.telegram_id == message.from_user.id).first()
        if existing_user:
            await message.answer("❌ Вы уже зарегистрированы!", reply_markup=get_main_keyboard("user"))
            await state.clear()
            return
        
        ref_code = hashlib.md5(f"{message.from_user.id}_{datetime.now()}".encode()).hexdigest()[:10]
        
        user = User(
            telegram_id=message.from_user.id,
            username=message.from_user.username,
            first_name=message.from_user.first_name,
            last_name=message.from_user.last_name,
            role=UserRole.PENDING,
            admin_nick=nick,
            admin_password_hash=password,
            referral_link=ref_code,
            form_data={"answers": answers}
        )
        session.add(user)
        session.flush()
        
        referral = Referral(owner_id=user.id)
        session.add(referral)
        
        application = Application(
            user_id=user.id,
            answers=answers,
            status="pending"
        )
        session.add(application)
        
        referral_id = data.get('referral_id')
        if referral_id:
            user.referral_id = referral_id
            
            referrer_ref = session.query(Referral).filter(Referral.owner_id == referral_id).first()
            if referrer_ref:
                referrer_ref.registrations += 1
                
                referrer = session.query(User).filter(User.id == referral_id).first()
                if referrer:
                    bonus = 50
                    referrer.total_profit += bonus
                    referrer.daily_profit += bonus
                    
                    await bot.send_message(
                        referrer.telegram_id,
                        f"🎉 **По вашей реферальной ссылке зарегистрировался новый пользователь!**\n\n"
                        f"👤 @{message.from_user.username}\n"
                        f"💰 Вам начислено: +{bonus} ₽\n"
                        f"💎 Текущий баланс: {referrer.total_profit:,.0f} ₽",
                        parse_mode=None
                    )
        
        session.commit()
        
        admin_text = f"📋 НОВАЯ ЗАЯВКА!\n\n"
        admin_text += f"👤 Пользователь: @{message.from_user.username}\n"
        admin_text += f"🆔 ID: {message.from_user.id}\n"
        admin_text += f"📝 Ник админки: {nick}\n"
        admin_text += f"🔑 Пароль: {password}\n\n"
        admin_text += f"Ответы:\n"
        
        for i, answer in enumerate(answers, 1):
            admin_text += f"\n{i}. {QUESTIONS[i-1]}\n   → {answer}\n"
        
        asyncio.create_task(notify_admins(bot, ADMIN_IDS, admin_text, get_moderation_keyboard(user.id)))
        
        await message.answer(
            f"✅ **Заявка отправлена на модерацию!**\n\n"
            f"**Ваши данные для админ-панели:**\n"
            f"└ Ник: `{nick}`\n"
            f"└ Пароль: `{password}`\n\n"
            f"⏳ **Статус:** Ожидает рассмотрения\n\n"
            f"Мы уведомим вас, когда заявка будет рассмотрена.",
            parse_mode=None,
            reply_markup=get_main_keyboard("user")
        )
        await state.clear()
        
    except Exception as e:
        session.rollback()
        logger.error(f"Error: {e}")
        await message.answer(f"❌ Ошибка при сохранении: {e}")
    finally:
        session.close()

@router.callback_query(F.data.startswith("approve_"))
async def approve_user(callback: CallbackQuery, bot: Bot):
    user_id = int(callback.data.split("_")[1])
    
    session = db.get_session()
    try:
        user = session.query(User).filter(User.id == user_id).first()
        if user and user.role == UserRole.PENDING:
            user.role = UserRole.USER
            user.date_joined = datetime.now()
            
            app = session.query(Application).filter(Application.user_id == user.id).first()
            if app:
                app.status = "approved"
                app.moderated_by = callback.from_user.id
                app.moderated_at = datetime.now()
            
            session.commit()
            
            # ========== СОЗДАНИЕ ПОЛЬЗОВАТЕЛЯ В КАЗИНО ==========
            if casino_api.enabled:
                email = f"user_{user.telegram_id}@catswill.local"
                casino_user = casino_api.create_user(email, user.username)
                
                if casino_user:
                    user.casino_email = casino_user["email"]
                    user.casino_password = casino_user["password"]
                    session.commit()
                    
                    await bot.send_message(
                        user.telegram_id,
                        f"🎰 **Аккаунт в казино создан!**\n\n"
                        f"📧 Логин: `{casino_user['email']}`\n"
                        f"🔑 Пароль: `{casino_user['password']}`\n\n"
                        f"🔗 Ссылка: https://catswill.casino",
                        parse_mode=None
                    )
                else:
                    await bot.send_message(
                        user.telegram_id,
                        "⚠️ Не удалось создать аккаунт в казино. Обратитесь к администратору.",
                        parse_mode=None
                    )
            # ====================================================
            
            await bot.send_message(
                user.telegram_id,
                "🎉 **Поздравляем! Ваша заявка одобрена!**\n\n"
                "Теперь вам доступны все функции бота.\n\n"
                "👇 Используйте кнопки ниже:",
                parse_mode=None,
                reply_markup=get_main_keyboard(user.role.value)
            )
            
            await callback.message.edit_text(
                callback.message.text + "\n\n✅ **ЗАЯВКА ОДОБРЕНА!**",
                parse_mode=None,
                reply_markup=None
            )
            await callback.answer("✅ Пользователь принят!")
        else:
            await callback.answer("Заявка уже обработана!", show_alert=True)
    finally:
        session.close()

@router.callback_query(F.data.startswith("reject_"))
async def reject_user(callback: CallbackQuery, bot: Bot):
    user_id = int(callback.data.split("_")[1])
    
    session = db.get_session()
    try:
        user = session.query(User).filter(User.id == user_id).first()
        if user and user.role == UserRole.PENDING:
            user.role = UserRole.BANNED
            
            app = session.query(Application).filter(Application.user_id == user.id).first()
            if app:
                app.status = "rejected"
                app.moderated_by = callback.from_user.id
                app.moderated_at = datetime.now()
            
            session.commit()
            
            await bot.send_message(
                user.telegram_id,
                "❌ **К сожалению, ваша заявка отклонена.**\n\n"
                "Вы можете подать заявку снова через 30 дней.",
                parse_mode=None
            )
            
            await callback.message.edit_text(
                callback.message.text + "\n\n❌ **ЗАЯВКА ОТКЛОНЕНА!**",
                parse_mode=None,
                reply_markup=None
            )
            await callback.answer("❌ Заявка отклонена!")
        else:
            await callback.answer("Заявка уже обработана!", show_alert=True)
    finally:
        session.close()

@router.callback_query(F.data.startswith("view_"))
async def view_application(callback: CallbackQuery):
    try:
        parts = callback.data.split("_")
        if len(parts) < 2:
            await callback.answer("❌ Неверный формат", show_alert=True)
            return
        
        user_id_str = parts[1]
        if user_id_str == "user":
            await callback.answer("❌ Неверный формат", show_alert=True)
            return
        
        user_id = int(user_id_str)
        
        session = db.get_session()
        try:
            user = session.query(User).filter(User.id == user_id).first()
            if user:
                text = f"📋 **Детали заявки**\n\n"
                text += f"👤 Пользователь: @{user.username}\n"
                text += f"🆔 ID: {user.telegram_id}\n"
                text += f"📝 Ник админки: {user.admin_nick}\n"
                text += f"🔑 Пароль: `{user.admin_password_hash}`\n\n"
                text += f"**Ответы на вопросы:**\n"
                
                if user.form_data and "answers" in user.form_data:
                    for i, answer in enumerate(user.form_data["answers"], 1):
                        text += f"\n*{i}. {QUESTIONS[i-1]}*\n   → {answer}\n"
                
                await callback.message.answer(text, parse_mode=None)
                await callback.answer()
        finally:
            session.close()
    except Exception as e:
        logger.error(f"Error in view_application: {e}")
        await callback.answer("❌ Ошибка", show_alert=True)