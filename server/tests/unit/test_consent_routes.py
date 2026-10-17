from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from api.dependencies import get_current_user, get_db
from api.errors import ApiError, ErrorCode
from api.routes.consent import consent, get_my_consent
from core.terms import TERMS_VERSION
from main import app
from schemas.consent import ConsentRequest

_USER_ID = "user-123"


class TestGetMyConsent:
    @pytest.mark.parametrize("consented", [True, False])
    async def test_returns_the_current_version_and_whether_the_user_consented(self, consented: bool) -> None:
        has_consented = AsyncMock(return_value=consented)
        with patch("api.routes.consent.user_consent_repository.has_consented", new=has_consented):
            result = await get_my_consent(current_user_id=_USER_ID, db=MagicMock())

        assert result.terms_version == TERMS_VERSION
        assert result.consented is consented
        assert has_consented.await_args is not None
        assert has_consented.await_args.args[1:] == (_USER_ID, TERMS_VERSION)


class TestConsent:
    async def test_records_consent_to_the_current_version(self) -> None:
        record = AsyncMock()
        with patch("api.routes.consent.user_consent_repository.record", new=record):
            response = await consent(
                ConsentRequest(terms_version=TERMS_VERSION), current_user_id=_USER_ID, db=MagicMock()
            )

        assert response.status_code == 204
        assert record.await_args is not None
        assert record.await_args.args[1:] == (_USER_ID, TERMS_VERSION)

    async def test_rejects_consent_to_an_outdated_version(self) -> None:
        record = AsyncMock()
        with (
            patch("api.routes.consent.user_consent_repository.record", new=record),
            pytest.raises(ApiError) as exc_info,
        ):
            await consent(ConsentRequest(terms_version=TERMS_VERSION - 1), current_user_id=_USER_ID, db=MagicMock())

        assert exc_info.value.status_code == 409
        assert exc_info.value.code == ErrorCode.TERMS_VERSION_OUTDATED
        record.assert_not_awaited()

    def test_rejects_a_body_without_a_version(self) -> None:
        app.dependency_overrides[get_current_user] = lambda: _USER_ID
        app.dependency_overrides[get_db] = lambda: MagicMock()
        try:
            response = TestClient(app).post("/api/consents", json={})
        finally:
            app.dependency_overrides.clear()

        assert response.status_code == 422
