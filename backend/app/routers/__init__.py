from .auth import router as auth_router
from .whatsapp import router as whatsapp_router
from .voice_notes import router as voice_notes_router
from .reviewer import router as reviewer_router
from .phrases import router as phrases_router
from .admin import router as admin_router
from .profile import router as profile_router

__all__ = [
    "auth_router", "whatsapp_router", "voice_notes_router",
    "reviewer_router", "phrases_router", "admin_router", "profile_router",
]
