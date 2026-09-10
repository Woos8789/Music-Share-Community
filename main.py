from typing import List, Dict
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Depends, HTTPException, status
from sqlalchemy.orm import Session
import models, schemas
from database import get_db, engine, Base
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
import json

app = FastAPI(title="Music Taste Community Server", description="A community project for music enthusiasts.", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def read_index():
    return FileResponse("index.html")

Base.metadata.create_all(bind=engine)

class ConnectionManager:
    def __init__(self):
        self.active_connections: dict[int, dict[WebSocket, dict]] = {}

    async def connect(self, room_id: int, websocket: WebSocket, user_id: int, username: str, points: int = 0):
        await websocket.accept()
        if room_id not in self.active_connections:
            self.active_connections[room_id] = {}
        self.active_connections[room_id][websocket] = {
            "id": user_id,
            "username": username,
            "points": points
        }

    def disconnect(self, room_id: int, websocket: WebSocket):
        if room_id in self.active_connections and websocket in self.active_connections[room_id]:
            del self.active_connections[room_id][websocket]

    async def broadcast(self, room_id: int, message: str):
        if room_id in self.active_connections:
            for connection in list(self.active_connections[room_id].keys()):
                try:
                    await connection.send_text(message)
                except Exception:
                    pass

    def get_online_users(self, room_id: int):
        if room_id not in self.active_connections:
            return []
        users_map = {}
        for info in self.active_connections[room_id].values():
            users_map[info["id"]] = info
        return list(users_map.values())

manager = ConnectionManager()

@app.post("/users/", response_model=schemas.UserResponse, status_code=status.HTTP_201_CREATED)
def create_user(user: schemas.UserCreate, db: Session = Depends(get_db)):
    if db.query(models.User).filter(models.User.email == user.email).first():
        raise HTTPException(status_code=400, detail="이미 등록된 이메일입니다.")
    if db.query(models.User).filter(models.User.username == user.username).first():
        raise HTTPException(status_code=400, detail="이미 사용 중인 닉네임입니다.")

    fake_hashed_password = user.password + "notsecure"
    new_user = models.User(
        username=user.username,
        email=user.email,
        hashed_password=fake_hashed_password,
        music_genre_tags=user.music_genre_tags,
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return new_user

@app.post("/login")
def login(data: dict, db: Session = Depends(get_db)):
    email = data.get("email")
    password = data.get("password")
    
    user = db.query(models.User).filter(models.User.email == email).first()
    if not user:
        raise HTTPException(status_code=404, detail="존재하지 않는 이메일입니다.")
    
    if user.hashed_password != password + "notsecure":
        raise HTTPException(status_code=400, detail="비밀번호가 올바르지 않습니다.")
        
    return {"id": user.id, "username": user.username, "email": user.email}

@app.websocket("/ws/chat/{room_id}/{user_id}")
async def websocket_endpoint(
    websocket: WebSocket,
    room_id: int,
    user_id: int,
    db: Session = Depends(get_db)
):
    user = db.query(models.User).filter(models.User.id == user_id).first()
    username = user.username if user else f"User {user_id}"
    points = getattr(user, 'points', 0)

    await manager.connect(room_id, websocket, user_id, username, points)

    async def broadcast_user_list():
        online_users = manager.get_online_users(room_id)
        payload = json.dumps({"type": "user_list", "users": online_users})
        await manager.broadcast(room_id, payload)

    past_messages = (
        db.query(models.Message)
        .filter(models.Message.room_id == room_id)
        .order_by(models.Message.id.asc())
        .limit(50)
        .all()
    )
    for msg in past_messages:
        msg_user = db.query(models.User).filter(models.User.id == msg.user_id).first()
        msg_username = msg_user.username if msg_user else f"User {msg.user_id}"
        await websocket.send_text(f"{msg_username}: {msg.content}")

    await manager.broadcast(room_id, f"system: {username} 님이 입장하셨습니다.")
    await broadcast_user_list()

    try:
        while True:
            data = await websocket.receive_text()

            db_message = models.Message(room_id=room_id, user_id=user_id, content=data)
            db.add(db_message)
            db.commit()

            broadcast_payload = f"{username}: {data}"
            await manager.broadcast(room_id, broadcast_payload)

    except WebSocketDisconnect:
        manager.disconnect(room_id, websocket)
        await manager.broadcast(room_id, f"system: {username} 님이 퇴장하셨습니다.")
        await broadcast_user_list()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000, reload=True)