from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials

from api.dependencies import get_account_deletion_user, get_current_user


def _make_credentials(token: str = "dummy-token") -> MagicMock:
    mock = MagicMock(spec=HTTPAuthorizationCredentials)
    mock.credentials = token
    return mock


class TestGetCurrentUser:
    async def test_valid_token_returns_user_id(self) -> None:
        credentials = _make_credentials()

        with patch("api.dependencies.verify_jwt", return_value={"sub": "user-123"}):
            result = await get_current_user(credentials)

        assert result == "user-123"

    async def test_verify_jwt_raises_value_error_returns_401(self) -> None:
        credentials = _make_credentials()

        with (
            patch("api.dependencies.verify_jwt", side_effect=ValueError("Token expired")),
            pytest.raises(HTTPException) as exc_info,
        ):
            await get_current_user(credentials)

        assert exc_info.value.status_code == 401
        assert exc_info.value.detail == "Token expired"

    async def test_payload_missing_sub_returns_401(self) -> None:
        credentials = _make_credentials()

        with (
            patch("api.dependencies.verify_jwt", return_value={}),
            pytest.raises(HTTPException) as exc_info,
        ):
            await get_current_user(credentials)

        assert exc_info.value.status_code == 401

    async def test_empty_token_returns_401(self) -> None:
        credentials = _make_credentials(token="")

        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(credentials)

        assert exc_info.value.status_code == 401


class TestGetAccountDeletionUser:
    async def test_token_for_account_deletion_returns_user_id(self) -> None:
        with patch("api.dependencies.verify_jwt", return_value={"sub": "user-123", "purpose": "account-deletion"}):
            result = await get_account_deletion_user(_make_credentials())

        assert result == "user-123"

    async def test_ordinary_token_returns_403(self) -> None:
        with (
            patch("api.dependencies.verify_jwt", return_value={"sub": "user-123"}),
            pytest.raises(HTTPException) as exc_info,
        ):
            await get_account_deletion_user(_make_credentials())

        assert exc_info.value.status_code == 403

    async def test_invalid_token_returns_401(self) -> None:
        with (
            patch("api.dependencies.verify_jwt", side_effect=ValueError("Token expired")),
            pytest.raises(HTTPException) as exc_info,
        ):
            await get_account_deletion_user(_make_credentials())

        assert exc_info.value.status_code == 401
