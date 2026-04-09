from handlers.start import router as start_router
from handlers.profile import router as profile_router
from handlers.admin import router as admin_router
from handlers.moderator import router as moderator_router

__all__ = ['start_router', 'profile_router', 'admin_router', 'moderator_router']