from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

import asyncpg
import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from api.routes.note_collection import (
    create_collection,
    delete_collection,
    get_collection,
    list_collections,
    rename_collection,
)
from schemas.note_collection import CollectionCreate, CollectionRename

_USER_ID = "user-123"
_NOW = datetime(2026, 10, 3, tzinfo=UTC)


def _collection(collection_id: UUID | None = None, name: str = "Linuxのしくみ") -> dict[str, object]:
    return {"id": collection_id or uuid4(), "user_id": _USER_ID, "name": name, "created_at": _NOW, "updated_at": _NOW}


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
