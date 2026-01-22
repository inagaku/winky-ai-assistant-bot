"""Tests for user caching utilities."""

import pytest
from unittest.mock import AsyncMock, MagicMock

from app.bot.user_cache import get_cached_user, invalidate_user_cache, update_cached_user, CACHED_USER_KEY


@pytest.fixture
def mock_context():
    """Create mock context with user_data."""
    context = MagicMock()
    context.user_data = {}
    return context


@pytest.fixture
def mock_update():
    """Create mock update with effective_user."""
    update = MagicMock()
    update.effective_user.id = 12345
    update.effective_user.username = "testuser"
    update.effective_user.first_name = "Test"
    update.effective_user.last_name = "User"
    return update


@pytest.fixture
def mock_user():
    """Create mock user object."""
    user = MagicMock()
    user.telegram_id = 12345
    user.preferences.language = "en"
    user.preferences.timezone = "UTC"
    return user


@pytest.fixture
def mock_user_service(mock_user):
    """Create mock user service."""
    service = AsyncMock()
    service.get_or_create_user.return_value = mock_user
    return service


@pytest.mark.asyncio
async def test_get_cached_user_fetches_from_db_on_cache_miss(
    mock_update, mock_context, mock_user_service, mock_user
):
    """First call should fetch from DB and cache."""
    result = await get_cached_user(mock_update, mock_context, mock_user_service)

    assert result == mock_user
    assert mock_context.user_data[CACHED_USER_KEY] == mock_user
    mock_user_service.get_or_create_user.assert_called_once()


@pytest.mark.asyncio
async def test_get_cached_user_returns_cached_on_hit(
    mock_update, mock_context, mock_user_service, mock_user
):
    """Second call should return cached user without DB call."""
    # Pre-populate cache
    mock_context.user_data[CACHED_USER_KEY] = mock_user

    result = await get_cached_user(mock_update, mock_context, mock_user_service)

    assert result == mock_user
    mock_user_service.get_or_create_user.assert_not_called()


def test_invalidate_user_cache_clears_cache(mock_context, mock_user):
    """Invalidate should remove cached user."""
    mock_context.user_data[CACHED_USER_KEY] = mock_user

    invalidate_user_cache(mock_context)

    assert CACHED_USER_KEY not in mock_context.user_data


def test_invalidate_user_cache_noop_when_empty(mock_context):
    """Invalidate should not fail when cache is empty."""
    invalidate_user_cache(mock_context)  # Should not raise

    assert CACHED_USER_KEY not in mock_context.user_data


def test_update_cached_user_sets_cache(mock_context, mock_user):
    """Update should set the cached user."""
    update_cached_user(mock_context, mock_user)

    assert mock_context.user_data[CACHED_USER_KEY] == mock_user
