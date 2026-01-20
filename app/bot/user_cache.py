"""User caching utilities for telegram handlers.

Caches User objects in context.user_data to avoid repeated database calls.
Cache is invalidated when user changes settings.
"""

from telegram import Update
from telegram.ext import ContextTypes

from app.models import User
from app.services import UserService

# Key for storing cached user in context.user_data
CACHED_USER_KEY = "cached_user"


async def get_cached_user(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    user_service: UserService,
) -> User:
    """Get user from cache or fetch from DB and cache.

    Args:
        update: Telegram update with effective_user
        context: Callback context with user_data
        user_service: Service to fetch user from DB

    Returns:
        User object (from cache or freshly fetched)
    """
    # Check cache first
    if CACHED_USER_KEY in context.user_data:
        return context.user_data[CACHED_USER_KEY]

    # Fetch from DB
    telegram_user = update.effective_user
    user = await user_service.get_or_create_user(
        telegram_id=telegram_user.id,
        username=telegram_user.username,
        first_name=telegram_user.first_name,
        last_name=telegram_user.last_name,
        language_code=telegram_user.language_code,
    )

    # Cache and return
    context.user_data[CACHED_USER_KEY] = user
    return user


def invalidate_user_cache(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Clear cached user from context.

    Call this after user preferences change (timezone, language).

    Args:
        context: Callback context with user_data
    """
    context.user_data.pop(CACHED_USER_KEY, None)


def update_cached_user(context: ContextTypes.DEFAULT_TYPE, user: User) -> None:
    """Update the cached user with new data.

    Call this after user preferences change to update cache
    instead of invalidating.

    Args:
        context: Callback context with user_data
        user: Updated user object
    """
    context.user_data[CACHED_USER_KEY] = user
