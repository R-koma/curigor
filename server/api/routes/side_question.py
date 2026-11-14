from uuid import UUID

from fastapi import APIRouter, status
from fastapi.responses import StreamingResponse

from api.dependencies import ConsentedUser
from api.errors import ApiError, ErrorCode
from core.database import get_pool
from repositories import dialogue_session_repository, side_question_repository
from schemas.side_question import (
    SideMessageResponse,
    SideQuestionCreate,
    SideQuestionFollowUp,
    SideQuestionResponse,
    SideQuestionsResponse,
)
from services import side_question as side_question_service

router = APIRouter(prefix="/api", tags=["side-questions"])

_NDJSON = "application/x-ndjson"


@router.get("/dialogue-sessions/{session_id}/side-questions", response_model=SideQuestionsResponse)
async def list_side_questions(session_id: UUID, current_user_id: ConsentedUser) -> SideQuestionsResponse:
    pool = await get_pool()
    async with pool.acquire() as conn:
        session = await dialogue_session_repository.find_by_id(conn, session_id, current_user_id)
        if session is None:
            raise ApiError(status.HTTP_404_NOT_FOUND, ErrorCode.SESSION_NOT_FOUND, "Session not found")
        threads = await side_question_repository.find_threads(conn, session_id)
    return SideQuestionsResponse(
        side_questions=[
            SideQuestionResponse(
                id=t["id"],
                parent_id=t["parent_id"],
                anchor_message_id=t["anchor_message_id"],
                anchor_side_message_id=t["anchor_side_message_id"],
                quote=t["quote"],
                occurrence=t["occurrence"],
                depth=t["depth"],
                messages=[SideMessageResponse(**m) for m in t["messages"]],
            )
            for t in threads
        ]
    )


@router.post("/dialogue-sessions/{session_id}/side-questions")
async def create_side_question(
    session_id: UUID, body: SideQuestionCreate, current_user_id: ConsentedUser
) -> StreamingResponse:
    turn = await side_question_service.prepare_new(session_id, current_user_id, body)
    return StreamingResponse(side_question_service.stream_answer(turn), media_type=_NDJSON)


@router.post("/side-questions/{side_question_id}/messages")
async def ask_side_follow_up(
    side_question_id: UUID, body: SideQuestionFollowUp, current_user_id: ConsentedUser
) -> StreamingResponse:
    turn = await side_question_service.prepare_follow_up(side_question_id, current_user_id, body.content)
    return StreamingResponse(side_question_service.stream_answer(turn), media_type=_NDJSON)
