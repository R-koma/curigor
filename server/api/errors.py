import logging
from enum import StrEnum
from http import HTTPStatus

from fastapi import HTTPException, Request, status
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger(__name__)


class ErrorCode(StrEnum):
    NOT_AUTHENTICATED = "not_authenticated"
    INVALID_TOKEN = "invalid_token"  # noqa: S105
    TOKEN_NOT_FOR_ACCOUNT_DELETION = "token_not_for_account_deletion"  # noqa: S105
    CONSENT_REQUIRED = "consent_required"
    TERMS_VERSION_OUTDATED = "terms_version_outdated"
    NOTE_NOT_FOUND = "note_not_found"
    SESSION_NOT_FOUND = "session_not_found"
    COLLECTION_NOT_FOUND = "collection_not_found"
    SYNTHESIS_NOT_FOUND = "synthesis_not_found"
    STUDY_MEMO_NOT_FOUND = "study_memo_not_found"
    REVIEW_SCHEDULE_NOT_FOUND = "review_schedule_not_found"
    LINK_NOT_FOUND = "link_not_found"
    IMAGE_NOT_FOUND = "image_not_found"
    COLLECTION_NAME_TAKEN = "collection_name_taken"
    COLLECTION_NOTE_COUNT_OUT_OF_RANGE = "collection_note_count_out_of_range"
    SYNTHESIS_FAILED = "synthesis_failed"
    AUDIO_EMPTY = "audio_empty"
    AUDIO_TOO_LARGE = "audio_too_large"
    UNSUPPORTED_AUDIO_FORMAT = "unsupported_audio_format"
    DAILY_TRANSCRIPTION_LIMIT_REACHED = "daily_transcription_limit_reached"
    TRANSCRIPTION_FAILED = "transcription_failed"
    TRANSCRIPT_TEXT_INVALID = "transcript_text_invalid"
    DAILY_TRANSCRIPT_FORMAT_LIMIT_REACHED = "daily_transcript_format_limit_reached"
    TRANSCRIPT_FORMAT_FAILED = "transcript_format_failed"
    SPEECH_TEXT_INVALID = "speech_text_invalid"
    DAILY_SPEECH_LIMIT_REACHED = "daily_speech_limit_reached"
    SPEECH_FAILED = "speech_failed"
    DAILY_SYNTHESIS_LIMIT_REACHED = "daily_synthesis_limit_reached"
    VALIDATION_ERROR = "validation_error"
    NOT_FOUND = "not_found"
    METHOD_NOT_ALLOWED = "method_not_allowed"
    HTTP_ERROR = "http_error"
    INTERNAL_ERROR = "internal_error"


_CODES_BY_STATUS: dict[int, ErrorCode] = {
    status.HTTP_401_UNAUTHORIZED: ErrorCode.NOT_AUTHENTICATED,
    status.HTTP_403_FORBIDDEN: ErrorCode.NOT_AUTHENTICATED,
    status.HTTP_404_NOT_FOUND: ErrorCode.NOT_FOUND,
    status.HTTP_405_METHOD_NOT_ALLOWED: ErrorCode.METHOD_NOT_ALLOWED,
}


class ApiError(HTTPException):
    def __init__(self, status_code: int, code: ErrorCode, detail: str) -> None:
        super().__init__(status_code=status_code, detail=detail)
        self.code = code


def error_body(code: ErrorCode, detail: str) -> dict[str, str]:
    return {"code": code, "detail": detail}


async def http_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, StarletteHTTPException)
    code = exc.code if isinstance(exc, ApiError) else _CODES_BY_STATUS.get(exc.status_code, ErrorCode.HTTP_ERROR)
    raw_detail: object = exc.detail
    detail = raw_detail if isinstance(raw_detail, str) else HTTPStatus(exc.status_code).phrase
    return JSONResponse(status_code=exc.status_code, content=error_body(code, detail), headers=exc.headers)


async def validation_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, RequestValidationError)
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        content={
            **error_body(ErrorCode.VALIDATION_ERROR, "Invalid request"),
            "errors": jsonable_encoder(exc.errors()),
        },
    )


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """未捕捉例外をログに残しつつ、スタックトレースを秘匿した 500 を返す。"""
    logger.exception("Unhandled exception on %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=error_body(ErrorCode.INTERNAL_ERROR, "Internal server error"),
    )
