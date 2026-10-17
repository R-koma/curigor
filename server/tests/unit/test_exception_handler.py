import json

from fastapi import FastAPI, HTTPException, status
from fastapi.exceptions import RequestValidationError
from fastapi.testclient import TestClient
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.requests import Request

from api.errors import (
    ApiError,
    ErrorCode,
    http_exception_handler,
    unhandled_exception_handler,
    validation_exception_handler,
)
from main import app


def _make_request(method: str = "GET", path: str = "/api/notes") -> Request:
    scope = {
        "type": "http",
        "method": method,
        "path": path,
        "headers": [],
    }
    return Request(scope)


class TestUnhandledExceptionHandler:
    async def test_returns_500_with_generic_detail(self) -> None:
        response = await unhandled_exception_handler(_make_request(), RuntimeError("boom"))

        assert response.status_code == 500
        assert json.loads(bytes(response.body)) == {"code": "internal_error", "detail": "Internal server error"}

    async def test_does_not_leak_exception_message(self) -> None:
        secret = "sensitive-internal-detail"
        response = await unhandled_exception_handler(_make_request(), ValueError(secret))

        assert secret not in bytes(response.body).decode()


def _app_with_handlers() -> FastAPI:
    app = FastAPI()
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)

    @app.get("/api-error")
    async def api_error() -> None:
        raise ApiError(status.HTTP_404_NOT_FOUND, ErrorCode.NOTE_NOT_FOUND, "Note not found")

    @app.get("/plain-error")
    async def plain_error() -> None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail={"nested": True})

    @app.get("/items/{item_id}")
    async def item(item_id: int) -> int:
        return item_id

    return app


class TestErrorShape:
    def test_api_error_carries_its_code_and_detail(self) -> None:
        res = TestClient(_app_with_handlers()).get("/api-error")

        assert res.status_code == 404
        assert res.json() == {"code": "note_not_found", "detail": "Note not found"}

    def test_a_plain_http_exception_gets_a_code_and_a_string_detail(self) -> None:
        res = TestClient(_app_with_handlers()).get("/plain-error")

        assert res.status_code == 409
        assert res.json() == {"code": "http_error", "detail": "Conflict"}

    def test_a_validation_error_keeps_the_field_errors_beside_a_string_detail(self) -> None:
        res = TestClient(_app_with_handlers()).get("/items/abc")

        body = res.json()
        assert res.status_code == 422
        assert body["code"] == "validation_error"
        assert body["detail"] == "Invalid request"
        assert body["errors"][0]["loc"] == ["path", "item_id"]

    def test_the_app_answers_an_unknown_route_with_a_code(self) -> None:
        res = TestClient(app).get("/api/no-such-route")

        assert res.status_code == 404
        assert res.json() == {"code": "not_found", "detail": "Not Found"}

    def test_the_app_answers_a_missing_token_with_a_code(self) -> None:
        res = TestClient(app).get("/api/notes")

        assert res.status_code in (401, 403)
        assert res.json()["code"] == "not_authenticated"
