from typing import Literal

from pydantic import BaseModel

HintId = Literal[
    "dashboard",
    "learn_start",
    "intake_card",
    "chat_input",
    "dialogue",
    "end_session",
    "note_detail",
]


class HintDismissalsResponse(BaseModel):
    dismissed: list[str]
