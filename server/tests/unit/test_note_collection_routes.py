from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

import asyncpg
import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from api.routes.note_collection import (
    create_collection,
    create_synthesis,
    delete_collection,
    get_collection,
    get_synthesis,
    list_collections,
    rename_collection,
)
from schemas.note_collection import CollectionCreate, CollectionRename
from services.collection_synthesis import CollectionNotFoundError, NoteCountError, SynthesisGenerationError

_USER_ID = "user-123"
_NOW = datetime(2026, 10, 3, tzinfo=UTC)


def _collection(collection_id: UUID | None = None, name: str = "Linuxのしくみ") -> dict[str, object]:
    return {"id": collection_id or uuid4(), "user_id": _USER_ID, "name": name, "created_at": _NOW, "updated_at": _NOW}


def _pool() -> MagicMock:
    acquire_cm = AsyncMock()
    acquire_cm.__aenter__ = AsyncMock(return_value=AsyncMock())
    acquire_cm.__aexit__ = AsyncMock(return_value=False)
    pool = MagicMock()
    pool.acquire = MagicMock(return_value=acquire_cm)
    return pool


class TestCreateCollection:
    async def test_strips_the_name(self) -> None:
        with patch(
            "api.routes.note_collection.note_collection_repository.get_or_create",
            AsyncMock(return_value=_collection()),
        ) as mock_create:
            await create_collection(
                CollectionCreate(name="  Linuxのしくみ "), current_user_id=_USER_ID, db=MagicMock()
            )

        assert mock_create.call_args.args[2] == "Linuxのしくみ"

    def test_rejects_a_blank_name(self) -> None:
        with pytest.raises(ValidationError):
            CollectionCreate(name="   ")


class TestListCollections:
    async def test_returns_note_counts(self) -> None:
        records = [{**_collection(), "note_count": 3}]
        with patch(
            "api.routes.note_collection.note_collection_repository.find_by_user_id", AsyncMock(return_value=records)
        ):
            result = await list_collections(current_user_id=_USER_ID, db=MagicMock())

        assert result.collections[0].note_count == 3


class TestGetCollection:
    async def test_marks_established_notes(self) -> None:
        collection_id = uuid4()
        notes = [
            {
                "id": uuid4(),
                "topic": "プロセス",
                "summary": "s",
                "status": "active",
                "created_at": _NOW,
                "review_count": 5,
            },
            {
                "id": uuid4(),
                "topic": "シグナル",
                "summary": None,
                "status": "active",
                "created_at": _NOW,
                "review_count": 1,
            },
        ]
        with (
            patch(
                "api.routes.note_collection.note_collection_repository.find_by_id",
                AsyncMock(return_value=_collection(collection_id)),
            ),
            patch("api.routes.note_collection.note_repository.find_by_collection_id", AsyncMock(return_value=notes)),
        ):
            result = await get_collection(collection_id, current_user_id=_USER_ID, db=MagicMock())

        assert [n.is_established for n in result.notes] == [True, False]

    async def test_missing_collection_is_404(self) -> None:
        with patch("api.routes.note_collection.note_collection_repository.find_by_id", AsyncMock(return_value=None)):
            with pytest.raises(HTTPException) as exc:
                await get_collection(uuid4(), current_user_id=_USER_ID, db=MagicMock())

        assert exc.value.status_code == 404


class TestRenameCollection:
    async def test_duplicate_name_is_409(self) -> None:
        with patch(
            "api.routes.note_collection.note_collection_repository.rename",
            AsyncMock(side_effect=asyncpg.UniqueViolationError("duplicate")),
        ):
            with pytest.raises(HTTPException) as exc:
                await rename_collection(uuid4(), CollectionRename(name="A"), current_user_id=_USER_ID, db=MagicMock())

        assert exc.value.status_code == 409


class TestDeleteCollection:
    async def test_missing_collection_is_404(self) -> None:
        with patch("api.routes.note_collection.note_collection_repository.delete", AsyncMock(return_value=False)):
            with pytest.raises(HTTPException) as exc:
                await delete_collection(uuid4(), current_user_id=_USER_ID, db=MagicMock())

        assert exc.value.status_code == 404


def _synthesis_record(collection_id: UUID, note_id: UUID, content_hash: str) -> dict[str, object]:
    return {
        "collection_id": collection_id,
        "content": "まとめ",
        "connections": [{"id": "c1", "title": "t", "note_ids": [str(note_id)], "explanation": "e", "question": "q"}],
        "contradictions": [],
        "gaps": [],
        "source_notes": [{"note_id": str(note_id), "content_hash": content_hash}],
        "generated_at": _NOW,
    }


class TestGetSynthesis:
    async def test_reports_a_changed_note(self) -> None:
        collection_id, note_id = uuid4(), uuid4()
        rows = [{"id": note_id, "topic": "T", "content": "更新後", "revisions": []}]
        with (
            patch(
                "api.routes.note_collection.collection_synthesis_repository.find_by_collection_id",
                AsyncMock(return_value=_synthesis_record(collection_id, note_id, "古いハッシュ")),
            ),
            patch(
                "api.routes.note_collection.note_repository.find_contents_by_collection_id",
                AsyncMock(return_value=rows),
            ),
            patch(
                "api.routes.note_collection.synthesis_insight_repository.find_by_collection_id",
                AsyncMock(return_value=[]),
            ),
        ):
            result = await get_synthesis(collection_id, current_user_id=_USER_ID, db=MagicMock())

        assert result.is_stale is True
        assert result.changed_note_ids == [note_id]

    async def test_includes_insights(self) -> None:
        collection_id, note_id = uuid4(), uuid4()
        insight = {"id": uuid4(), "connection_title": "t", "content": "説明", "created_at": _NOW}
        with (
            patch(
                "api.routes.note_collection.collection_synthesis_repository.find_by_collection_id",
                AsyncMock(return_value=_synthesis_record(collection_id, note_id, "h")),
            ),
            patch(
                "api.routes.note_collection.note_repository.find_contents_by_collection_id",
                AsyncMock(return_value=[]),
            ),
            patch(
                "api.routes.note_collection.synthesis_insight_repository.find_by_collection_id",
                AsyncMock(return_value=[insight]),
            ),
        ):
            result = await get_synthesis(collection_id, current_user_id=_USER_ID, db=MagicMock())

        assert [i.content for i in result.insights] == ["説明"]

    async def test_missing_synthesis_is_404(self) -> None:
        with patch(
            "api.routes.note_collection.collection_synthesis_repository.find_by_collection_id",
            AsyncMock(return_value=None),
        ):
            with pytest.raises(HTTPException) as exc:
                await get_synthesis(uuid4(), current_user_id=_USER_ID, db=MagicMock())

        assert exc.value.status_code == 404


class TestCreateSynthesis:
    @pytest.mark.parametrize(
        ("error", "status_code"),
        [(CollectionNotFoundError(), 404), (NoteCountError(), 422), (SynthesisGenerationError(), 502)],
    )
    async def test_maps_errors(self, error: Exception, status_code: int) -> None:
        with patch("api.routes.note_collection.generate_synthesis", AsyncMock(side_effect=error)):
            with pytest.raises(HTTPException) as exc:
                await create_synthesis(uuid4(), current_user_id=_USER_ID)

        assert exc.value.status_code == status_code

    async def test_fresh_draft_is_not_stale(self) -> None:
        collection_id, note_id = uuid4(), uuid4()
        with (
            patch(
                "api.routes.note_collection.generate_synthesis",
                AsyncMock(return_value=_synthesis_record(collection_id, note_id, "h")),
            ),
            patch("api.routes.note_collection.get_pool", AsyncMock(return_value=_pool())),
            patch(
                "api.routes.note_collection.synthesis_insight_repository.find_by_collection_id",
                AsyncMock(return_value=[]),
            ),
        ):
            result = await create_synthesis(collection_id, current_user_id=_USER_ID)

        assert result.is_stale is False
        assert result.connections[0].title == "t"
