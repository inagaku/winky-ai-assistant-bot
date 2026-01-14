-- Migration: 002_add_user_preferences
-- Description: Add telegram_language_code to users and create minimal user_preferences table
-- Created: 2026-01-13

-- Add telegram_language_code to users table (captured from Telegram API)
ALTER TABLE users ADD COLUMN IF NOT EXISTS telegram_language_code VARCHAR(10);

-- User preferences table (minimal - only user-configurable settings)
CREATE TABLE IF NOT EXISTS user_preferences (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID UNIQUE NOT NULL REFERENCES users(id) ON DELETE CASCADE,

    -- User-configurable preferences
    preferred_language VARCHAR(10) DEFAULT 'en',        -- ISO 639-1 code (en, es, de, etc.)
    timezone VARCHAR(50) DEFAULT 'UTC',                 -- IANA timezone (America/New_York, etc.)

    -- Metadata
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Index for quick lookup by user
CREATE INDEX IF NOT EXISTS idx_user_preferences_user_id ON user_preferences(user_id);

-- Apply updated_at trigger
DROP TRIGGER IF EXISTS update_user_preferences_updated_at ON user_preferences;
CREATE TRIGGER update_user_preferences_updated_at
    BEFORE UPDATE ON user_preferences
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Create default preferences for existing users (use telegram language_code if available)
INSERT INTO user_preferences (user_id, preferred_language, timezone)
SELECT id, COALESCE(telegram_language_code, language, 'en'), timezone
FROM users
WHERE NOT EXISTS (
    SELECT 1 FROM user_preferences WHERE user_preferences.user_id = users.id
);
