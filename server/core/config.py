import os

from dotenv import load_dotenv

load_dotenv()

DATABASE_URL: str | None = os.getenv("DATABASE_URL")
BETTER_AUTH_URL: str = os.getenv("BETTER_AUTH_URL", "http://localhost:3000")
JWKS_URL: str = os.getenv("JWKS_URL", f"{BETTER_AUTH_URL}/api/auth/jwks")

LANGFUSE_PUBLIC_KEY: str | None = os.getenv("LANGFUSE_PUBLIC_KEY") or None
LANGFUSE_SECRET_KEY: str | None = os.getenv("LANGFUSE_SECRET_KEY") or None
LANGFUSE_BASE_URL: str = os.getenv("LANGFUSE_BASE_URL", "https://cloud.langfuse.com")

LANGFUSE_TRACING_ENVIRONMENT: str = os.getenv("LANGFUSE_TRACING_ENVIRONMENT", "development")

STORAGE_BACKEND: str = os.getenv("STORAGE_BACKEND", "local")
LOCAL_STORAGE_DIR: str = os.getenv("LOCAL_STORAGE_DIR", "storage_data")

REVIEW_TIMEZONE: str = os.getenv("REVIEW_TIMEZONE", "Asia/Tokyo")

MAX_IMAGES_PER_MESSAGE: int = 4
MAX_IMAGE_BYTES: int = 5 * 1024 * 1024
ALLOWED_IMAGE_MIME_TYPES: frozenset[str] = frozenset({"image/jpeg", "image/png", "image/webp"})

TRANSCRIPTION_MODEL: str = os.getenv("TRANSCRIPTION_MODEL", "gpt-transcribe")
TRANSCRIPTION_LANGUAGE: str = "ja"
TRANSCRIPTION_TIMEOUT_SECONDS: float = 120.0
TRANSCRIPTION_MAX_RETRIES: int = 1
MAX_AUDIO_BYTES: int = 5 * 1024 * 1024
ALLOWED_AUDIO_MIME_TYPES: frozenset[str] = frozenset({"audio/webm", "audio/mp4"})
DAILY_TRANSCRIPTION_LIMIT: int = 100

SPEECH_MODEL: str = os.getenv("SPEECH_MODEL", "gpt-4o-mini-tts")
SPEECH_VOICE: str = os.getenv("SPEECH_VOICE", "coral")
SPEECH_INSTRUCTIONS: str = "落ち着いた丁寧な日本語で、聞き取りやすい速さで話してください。"
SPEECH_TIMEOUT_SECONDS: float = 60.0
SPEECH_MAX_RETRIES: int = 1
MAX_SPEECH_CHARS: int = 500
DAILY_SPEECH_CHAR_LIMIT: int = 30_000
