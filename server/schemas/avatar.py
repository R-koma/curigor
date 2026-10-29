from pydantic import BaseModel


class AvatarResponse(BaseModel):
    path: str
