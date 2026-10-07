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
ALLOWED_AUDIO_MIME_TYPES: frozenset[str] = frozenset({"audio/webm", "audio/mp4", "audio/wav"})
RECORDED_AUDIO_BYTES_PER_SECOND: int = 64_000 // 8
MAX_TRANSCRIPTION_PROMPT_CHARS: int = 200
DAILY_TRANSCRIPTION_SECONDS: int = 3 * 60 * 60

SPEECH_MODEL: str = os.getenv("SPEECH_MODEL", "gpt-4o-mini-tts")
SPEECH_VOICE: str = os.getenv("SPEECH_VOICE", "coral")
SPEECH_INSTRUCTIONS: str = "はきはきと自然なテンポの日本語で話してください。"
SPEECH_TIMEOUT_SECONDS: float = 60.0
SPEECH_MAX_RETRIES: int = 1
MAX_SPEECH_CHARS: int = 500
DAILY_SPEECH_CHAR_LIMIT: int = 30_000

EMBEDDING_MODEL: str = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")
EMBEDDING_DIMENSIONS: int = 1536  # note_embeddings.embedding の vector(1536) と一致させる
EMBEDDING_TIMEOUT_SECONDS: float = 30.0
EMBEDDING_MAX_RETRIES: int = 2
MAX_EMBEDDING_INPUT_CHARS: int = 6000

COLLECTION_SUGGESTION_NEIGHBORS: int = 10
COLLECTION_SUGGESTION_MIN_SIMILARITY: float = 0.5

RELATED_NOTES_LIMIT: int = 3
RELATED_NOTES_MIN_SIMILARITY: float = 0.4
RELATED_NOTES_TIMEOUT_SECONDS: float = 5.0
MAX_RELATED_NOTE_SUMMARY_CHARS: int = 300
