from pydantic import BaseModel


class TopicCorrectionCard(BaseModel):
    previous_topic: str
    new_topic: str
