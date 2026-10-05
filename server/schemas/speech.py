from typing import Annotated
from uuid import UUID

from pydantic import AfterValidator, BaseModel

_ALLOWED_SPEEDS = frozenset({1.0, 1.25, 1.5})


def _check_speed(value: float) -> float:
    if value not in _ALLOWED_SPEEDS:
        raise ValueError("speed must be one of 1.0, 1.25, 1.5")
    return value


SpeechSpeed = Annotated[float, AfterValidator(_check_speed)]


class SpeechRequest(BaseModel):
    text: str
    dialogue_session_id: UUID
    speed: SpeechSpeed = 1.0
