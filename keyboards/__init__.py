from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton

def get_main_keyboard(role: str):
    """Главное меню в зависимости от роли"""
    buttons = [
        [KeyboardButton(text="👤 Профиль")],
        [KeyboardButton(text="💰 Выплаты"), KeyboardButton(text="📚 Информация")],
        [KeyboardButton(text="🛟 Поддержка")]
    ]
    
    if role in ["admin", "moderator"]:
        buttons.append([KeyboardButton(text="⚙️ Админ-панель")])
    
    if role == "moderator":
        buttons.append([KeyboardButton(text="🛡️ Модератор-панель")])
    
    return ReplyKeyboardMarkup(
        keyboard=buttons,
        resize_keyboard=True,
        input_field_placeholder="Выберите действие..."
    )

def get_profile_keyboard():
    """Клавиатура профиля"""
    buttons = [
        [KeyboardButton(text="💳 Установить кошелек")],
        [KeyboardButton(text="🔐 Показать пароль")],
        [KeyboardButton(text="💰 Запрос вывода")],
        [KeyboardButton(text="📊 Моя статистика")],
        [KeyboardButton(text="🔗 Реферальная ссылка")],
        [KeyboardButton(text="🔙 Главное меню")]
    ]
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)

def get_payments_keyboard():
    """Клавиатура выплат"""
    buttons = [
        [KeyboardButton(text="💳 Мои кошельки")],
        [KeyboardButton(text="💰 Запросить выплату")],
        [KeyboardButton(text="📋 История выплат")],
        [KeyboardButton(text="🔙 Главное меню")]
    ]
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)

def get_support_keyboard():
    """Клавиатура поддержки"""
    buttons = [
        [KeyboardButton(text="📝 Написать администратору")],
        [KeyboardButton(text="💬 Написать саппорту")],
        [KeyboardButton(text="🔙 Главное меню")]
    ]
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)

def get_info_keyboard():
    """Клавиатура информации"""
    buttons = [
        [KeyboardButton(text="📖 Мануалы")],
        [KeyboardButton(text="💬 Чаты")],
        [KeyboardButton(text="📜 Правила")],
        [KeyboardButton(text="🔙 Главное меню")]
    ]
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)

def get_admin_keyboard():
    """Клавиатура админ-панели"""
    buttons = [
        [KeyboardButton(text="📋 Модерация")],
        [KeyboardButton(text="👥 Пользователи")],
        [KeyboardButton(text="📊 Статистика")],
        [KeyboardButton(text="📨 Рассылка")],
        [KeyboardButton(text="💰 Выплаты")],
        [KeyboardButton(text="💵 Управление балансом")],
        [KeyboardButton(text="💳 Создать оплату")],
        [KeyboardButton(text="🔙 Главное меню")]
    ]
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)

def get_moderator_keyboard():
    """Клавиатура модератор-панели"""
    buttons = [
        [KeyboardButton(text="📋 Модерация заявок")],
        [KeyboardButton(text="📊 Статистика")],
        [KeyboardButton(text="🔙 Главное меню")]
    ]
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)

def get_subscription_keyboard():
    """Клавиатура для проверки подписки"""
    from config import REQUIRED_CHANNELS
    buttons = []
    
    for channel in REQUIRED_CHANNELS:
        if channel.get("url"):
            buttons.append([KeyboardButton(text=f"📢 Подписаться на {channel['name']}", url=channel["url"])])
    
    buttons.append([KeyboardButton(text="✅ Проверить подписку")])
    buttons.append([KeyboardButton(text="🔙 Главное меню")])
    
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)

def get_moderation_keyboard(user_id: int):
    """Инлайн-клавиатура для модерации заявки"""
    buttons = [
        [
            InlineKeyboardButton(text="✅ Принять", callback_data=f"approve_{user_id}"),
            InlineKeyboardButton(text="❌ Отклонить", callback_data=f"reject_{user_id}")
        ],
        [InlineKeyboardButton(text="👁️ Просмотр", callback_data=f"view_{user_id}")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_withdraw_keyboard(withdraw_id: int):
    """Клавиатура для модерации выплат"""
    buttons = [
        [
            InlineKeyboardButton(text="✅ Выплачено", callback_data=f"pay_{withdraw_id}"),
            InlineKeyboardButton(text="❌ Отказать", callback_data=f"reject_pay_{withdraw_id}")
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_user_management_keyboard(user_id: int):
    """Клавиатура управления пользователем"""
    buttons = [
        [
            InlineKeyboardButton(text="👑 Сделать админом", callback_data=f"make_admin_{user_id}"),
            InlineKeyboardButton(text="🛡️ Сделать модератором", callback_data=f"make_moderator_{user_id}")
        ],
        [
            InlineKeyboardButton(text="🔨 Заблокировать", callback_data=f"ban_{user_id}"),
            InlineKeyboardButton(text="🔓 Разблокировать", callback_data=f"unban_{user_id}")
        ],
        [InlineKeyboardButton(text="💰 Начислить баланс", callback_data=f"add_balance_{user_id}")],
        [InlineKeyboardButton(text="👁️ Просмотр", callback_data=f"view_user_{user_id}")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_back_keyboard():
    """Клавиатура с кнопкой назад в главное меню"""
    buttons = [[KeyboardButton(text="🔙 Главное меню")]]
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)