from pydantic import BaseModel


class ConsentStatusResponse(BaseModel):
    terms_version: int
    consented: bool


class ConsentRequest(BaseModel):
    terms_version: int
