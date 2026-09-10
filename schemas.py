from datetime import datetime
from typing import Optional
from pydantic import BaseModel, EmailStr

class UserBase(BaseModel):
    username: str
    email: EmailStr
    music_genre_tags: Optional[str] = None

class UserCreate(UserBase):
    password: str

class UserResponse(UserBase):
    id: int
    points: int
    created_at: datetime

    class Config:
        from_attributes = True

class MessageBase(BaseModel):
    content: str

class MessageCreate(MessageBase):
    room_id: int

class MessageResponse(MessageBase):
    id: int
    user_id: int
    room_id: int
    created_at: datetime

    class Config:
        from_attributes = True

class ChatRoomBase(BaseModel):
    title: str
    description: Optional[str] = None
    genre_tag: Optional[str] = None

class ChatRoomCreate(ChatRoomBase):
    pass

class ChatRoomResponse(ChatRoomBase):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True

