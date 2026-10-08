import importlib.util
from pathlib import Path
from typing import get_args
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient

from api.dependencies import get_current_user, get_db
from api.routes.hint import dismiss_hint, list_hint_dismissals, reset_hint_dismissals
from main import app
from schemas.hint import HintId

_USER_ID = "user-123"


class TestListHintDismissals:
    async def test_returns_dismissed_hint_ids(self) -> None:
        with patch(
            "api.routes.hint.hint_dismissal_repository.find_hint_ids_by_user",
            new=AsyncMock(return_value=["dashboard"]),
        ):
            result = await list_hint_dismissals(current_user_id=_USER_ID, db=MagicMock())

        assert result.dismissed == ["dashboard"]


class TestDismissHint:
    async def test_records_the_hint(self) -> None:
        mock_dismiss = AsyncMock()
        with patch("api.routes.hint.hint_dismissal_repository.dismiss", new=mock_dismiss):
            response = await dismiss_hint(hint_id="chat_input", current_user_id=_USER_ID, db=MagicMock())

        assert response.status_code == 204
        assert mock_dismiss.await_args is not None
        assert mock_dismiss.await_args.args[1:] == (_USER_ID, "chat_input")

    def test_rejects_unknown_hint_id(self) -> None:
        app.dependency_overrides[get_current_user] = lambda: _USER_ID
        app.dependency_overrides[get_db] = lambda: MagicMock()
        try:
            response = TestClient(app).put("/api/hints/dismissals/unknown")
        finally:
            app.dependency_overrides.clear()

        assert response.status_code == 422


class TestResetHintDismissals:
    async def test_deletes_the_users_dismissals(self) -> None:
        mock_delete = AsyncMock()
        with patch("api.routes.hint.hint_dismissal_repository.delete_all_by_user", new=mock_delete):
            response = await reset_hint_dismissals(current_user_id=_USER_ID, db=MagicMock())

        assert response.status_code == 204
        mock_delete.assert_awaited_once()


def test_backfill_covers_every_hint_id() -> None:
    path = Path(__file__).parents[2] / "migrations/versions/c7e1a9d3f5b2_create_user_hint_dismissals_table.py"
    spec = importlib.util.spec_from_file_location("hint_migration", path)
    assert spec is not None and spec.loader is not None
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)

    assert set(migration._HINT_IDS) == set(get_args(HintId))
