"""Simple translator for multi-language support."""

import json
import logging
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

# Default/fallback language
DEFAULT_LANGUAGE = "en"

# Directory containing locale files
LOCALES_DIR = Path(__file__).parent / "locales"


class Translator:
    """
    Simple translator that loads translations from JSON files.

    Usage:
        translator = Translator()
        message = translator.t("welcome", locale="es", name="John")
        # Returns: "¡Hola John! Soy tu asistente personal."
    """

    def __init__(self):
        self._translations: Dict[str, Dict[str, str]] = {}
        self._load_all_locales()

    def _load_all_locales(self) -> None:
        """Load all available locale files."""
        if not LOCALES_DIR.exists():
            logger.warning(f"Locales directory not found: {LOCALES_DIR}")
            return

        for locale_file in LOCALES_DIR.glob("*.json"):
            locale = locale_file.stem  # e.g., "en" from "en.json"
            try:
                with open(locale_file, "r", encoding="utf-8") as f:
                    self._translations[locale] = json.load(f)
                logger.info(f"Loaded locale: {locale} ({len(self._translations[locale])} keys)")
            except Exception as e:
                logger.error(f"Failed to load locale {locale}: {e}")

    def get_available_locales(self) -> list:
        """Get list of available locale codes."""
        return list(self._translations.keys())

    def t(
        self,
        key: str,
        locale: str = DEFAULT_LANGUAGE,
        **kwargs: Any,
    ) -> str:
        """
        Translate a key to the specified locale.

        Args:
            key: The translation key (e.g., "welcome", "reminder_created")
            locale: The locale code (e.g., "en", "es", "de")
            **kwargs: Variables to interpolate into the translation

        Returns:
            The translated string with variables interpolated
        """
        # Get translations for locale, fallback to default
        translations = self._translations.get(locale)
        if not translations:
            translations = self._translations.get(DEFAULT_LANGUAGE, {})

        # Get the translation string
        template = translations.get(key)
        if not template:
            # Try fallback language
            fallback = self._translations.get(DEFAULT_LANGUAGE, {})
            template = fallback.get(key)

        if not template:
            # Key not found - return the key itself
            logger.warning(f"Translation key not found: {key} (locale: {locale})")
            return key

        # Interpolate variables
        try:
            return template.format(**kwargs)
        except KeyError as e:
            logger.warning(f"Missing variable in translation: {e} (key: {key})")
            return template

    def reload(self) -> None:
        """Reload all translations from disk."""
        self._translations.clear()
        self._load_all_locales()


# Singleton instance
_translator_instance: Optional[Translator] = None


def get_translator() -> Translator:
    """Get or create the translator singleton."""
    global _translator_instance
    if _translator_instance is None:
        _translator_instance = Translator()
    return _translator_instance


def t(key: str, locale: str = DEFAULT_LANGUAGE, **kwargs: Any) -> str:
    """
    Convenience function to translate a key.

    Usage:
        from app.i18n import t
        message = t("welcome", locale=user.preferences.language, name=user.display_name)
    """
    return get_translator().t(key, locale, **kwargs)
