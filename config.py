import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN is not set in .env file")

ADMIN_IDS = [int(id.strip()) for id in os.getenv("ADMIN_IDS", "").split(",") if id.strip()]
MODERATOR_IDS = [int(id.strip()) for id in os.getenv("MODERATOR_IDS", "").split(",") if id.strip()]

SUPPORT_IDS = ADMIN_IDS + MODERATOR_IDS

MODERATION_CHAT_ID = os.getenv("MODERATION_CHAT_ID")
if MODERATION_CHAT_ID:
    MODERATION_CHAT_ID = int(MODERATION_CHAT_ID)

# MySQL настройки
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = int(os.getenv("DB_PORT", "3306"))
DB_USER = os.getenv("DB_USER", "root")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")
DB_NAME = os.getenv("DB_NAME", "ticket_bot")

# URL для MySQL
DATABASE_URL = "sqlite:///ticket_bot.db"

# Redis настройки
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
REDIS_DB = int(os.getenv("REDIS_DB", 0))

MIN_ADMIN_NICK_LENGTH = int(os.getenv("MIN_ADMIN_NICK_LENGTH", "10"))
MAX_ADMIN_NICK_LENGTH = int(os.getenv("MAX_ADMIN_NICK_LENGTH", "20"))

# Каналы для обязательной подписки
REQUIRED_CHANNELS = [
    {"id": os.getenv("CHANNEL_1_ID"), "name": "Основной канал", "url": os.getenv("CHANNEL_1_URL", "")},
    {"id": os.getenv("CHANNEL_2_ID"), "name": "Новостной канал", "url": os.getenv("CHANNEL_2_URL", "")},
    {"id": os.getenv("CHAT_ID"), "name": "Чат команды", "url": os.getenv("CHAT_URL", "")}
]
REQUIRED_CHANNELS = [c for c in REQUIRED_CHANNELS if c["id"]]

QUESTIONS = [
    "Как вас зовут?",
    "Сколько вам лет?",
    "Какой у вас опыт работы?",
    "Почему вы хотите вступить в команду?",
    "Какие ваши сильные стороны?"
]

print("✅ Конфигурация загружена (MySQL + Redis)")