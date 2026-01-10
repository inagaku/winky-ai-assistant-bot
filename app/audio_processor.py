"""
Audio processing module for converting audio files to text.
Uses OpenAI Whisper API.
"""
import logging
import os
from pathlib import Path
from typing import Optional

from openai import OpenAI

logger = logging.getLogger(__name__)


class AudioProcessor:
    """Handles audio file conversion to text using OpenAI Whisper."""

    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize the AudioProcessor.

        Args:
            api_key: OpenAI API key. If not provided, will use OPENAI_API_KEY env var.
        """
        self.client = OpenAI(api_key=api_key or os.getenv("OPENAI_API_KEY"))

    async def transcribe_audio(self, audio_file_path: str) -> str:
        """
        Transcribe audio file to text using Whisper.

        Args:
            audio_file_path: Path to the audio file.

        Returns:
            Transcribed text.

        Raises:
            FileNotFoundError: If audio file doesn't exist.
            Exception: If transcription fails.
        """
        file_path = Path(audio_file_path)

        if not file_path.exists():
            raise FileNotFoundError(f"Audio file not found: {audio_file_path}")

        try:
            logger.info(f"Transcribing audio file: {audio_file_path}")

            with open(file_path, "rb") as audio_file:
                transcript = self.client.audio.transcriptions.create(
                    model="whisper-1",
                    file=audio_file,
                    language="en"
                )

            text = transcript.text
            logger.info(f"Successfully transcribed audio. Length: {len(text)} chars")
            return text

        except Exception as e:
            logger.error(f"Error transcribing audio: {str(e)}")
            raise

    async def transcribe_audio_url(self, audio_url: str) -> str:
        """
        Transcribe audio from URL using Whisper.

        Args:
            audio_url: URL to the audio file.

        Returns:
            Transcribed text.

        Raises:
            Exception: If transcription fails.
        """
        try:
            logger.info(f"Transcribing audio from URL: {audio_url}")

            import httpx

            async with httpx.AsyncClient() as client:
                response = await client.get(audio_url)
                response.raise_for_status()

                # Save temporarily
                temp_path = "/tmp/audio_temp.ogg"
                with open(temp_path, "wb") as f:
                    f.write(response.content)

                with open(temp_path, "rb") as audio_file:
                    transcript = self.client.audio.transcriptions.create(
                        model="whisper-1",
                        file=audio_file,
                        language="en"
                    )

                # Clean up
                os.remove(temp_path)

                text = transcript.text
                logger.info(f"Successfully transcribed audio from URL. Length: {len(text)} chars")
                return text

        except Exception as e:
            logger.error(f"Error transcribing audio from URL: {str(e)}")
            raise

