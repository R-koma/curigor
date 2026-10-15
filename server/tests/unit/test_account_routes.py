from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient

from api.dependencies import get_account_deletion_user
from main import app

_USER_ID = "user-123"


def _client() -> TestClient:
    app.state.checkpointer = MagicMock()
    return TestClient(app, raise_server_exceptions=False)


def test_purges_the_current_users_data() -> None:
    app.dependency_overrides[get_account_deletion_user] = lambda: _USER_ID
    purge = AsyncMock()
    try:
        with (
            patch("api.routes.account.get_pool", new=AsyncMock(return_value=MagicMock())),
            patch("api.routes.account.purge_user_data", new=purge),
        ):
            response = _client().delete("/api/account/data")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 204
    assert purge.await_args is not None
    assert purge.await_args.args[3] == _USER_ID


def test_returns_500_when_the_purge_fails() -> None:
    app.dependency_overrides[get_account_deletion_user] = lambda: _USER_ID
    try:
        with (
            patch("api.routes.account.get_pool", new=AsyncMock(return_value=MagicMock())),
            patch("api.routes.account.purge_user_data", new=AsyncMock(side_effect=OSError("disk"))),
        ):
            response = _client().delete("/api/account/data")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 500


def test_requires_a_token() -> None:
    response = _client().delete("/api/account/data")

    assert response.status_code == 401


def test_rejects_an_ordinary_api_token() -> None:
    with patch("api.dependencies.verify_jwt", return_value={"sub": _USER_ID}):
        response = _client().delete("/api/account/data", headers={"Authorization": "Bearer ordinary"})

    assert response.status_code == 403
