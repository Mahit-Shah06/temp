from pydantic import BaseModel
from datetime import datetime

class DocumentBase(BaseModel):
    filename: str
    category: str
    author: str | None = None
    summary: str | None = None

class DocumentCreate(DocumentBase):
    filepath: str

class Document(DocumentBase):
    docid: int
    upload_date: datetime
    uuid: str
    class Config:
        from_attributes = True

class UserBase(BaseModel):
    username: str
    role: str

class UserCreate(UserBase):
    password: str

class User(UserBase):
    uuid: str

    class Config:
        from_attributes = True

class LoginRequest(BaseModel):
    username: str
    password: str

class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    username: str | None = None

class AccessLog(BaseModel):
    log_id: int
    user_uuid: str
    doc_uuid: str | None = None
    action: str
    timestamp: datetime

    class Config:
        from_attributes = True