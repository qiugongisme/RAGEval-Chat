import json
import os
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from config import config

router = APIRouter()

SESSIONS_FILE = os.path.join(config.DATA_DIR, "sessions.json")


def _read() -> list:
    if not os.path.exists(SESSIONS_FILE):
        return []
    with open(SESSIONS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def _write(data: list):
    os.makedirs(os.path.dirname(SESSIONS_FILE), exist_ok=True)
    with open(SESSIONS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


class SessionCreate(BaseModel):
    model_id: str = Field(..., min_length=1)
    kb_id: Optional[str] = None


class SessionUpdate(BaseModel):
    title: Optional[str] = None


class MessageItem(BaseModel):
    role: str
    content: str
    sources: list = []
    chunks: list = []


class MessagesSave(BaseModel):
    messages: list[MessageItem]


@router.get("")
async def list_sessions():
    """会话列表（仅元数据）"""
    sessions = _read()
    result = []
    for s in sessions:
        result.append({
            "id": s["id"],
            "title": s.get("title", "新对话"),
            "model_id": s.get("model_id", ""),
            "kb_id": s.get("kb_id"),
            "created_at": s.get("created_at", ""),
            "updated_at": s.get("updated_at", ""),
            "message_count": len(s.get("messages", [])),
        })
    result.sort(key=lambda x: x["updated_at"], reverse=True)
    return result


@router.post("")
async def create_session(data: SessionCreate):
    """创建新会话"""
    sessions = _read()
    now = datetime.now(timezone.utc).isoformat()
    session = {
        "id": str(uuid.uuid4()),
        "title": "新对话",
        "model_id": data.model_id,
        "kb_id": data.kb_id,
        "created_at": now,
        "updated_at": now,
        "messages": [],
    }
    sessions.append(session)
    _write(sessions)
    return {"id": session["id"]}


@router.put("/{session_id}")
async def update_session(session_id: str, data: SessionUpdate):
    """更新会话标题"""
    sessions = _read()
    for s in sessions:
        if s["id"] == session_id:
            if data.title is not None:
                s["title"] = data.title
            s["updated_at"] = datetime.now(timezone.utc).isoformat()
            _write(sessions)
            return {"status": "ok"}
    raise HTTPException(404, "会话不存在")


@router.delete("/{session_id}")
async def delete_session(session_id: str):
    """删除会话"""
    sessions = _read()
    new_sessions = [s for s in sessions if s["id"] != session_id]
    if len(new_sessions) == len(sessions):
        raise HTTPException(404, "会话不存在")
    _write(new_sessions)
    return {"status": "ok"}


@router.get("/{session_id}/messages")
async def get_session_messages(session_id: str):
    """获取会话消息列表"""
    sessions = _read()
    for s in sessions:
        if s["id"] == session_id:
            return s.get("messages", [])
    raise HTTPException(404, "会话不存在")


@router.put("/{session_id}/messages")
async def save_session_messages(session_id: str, data: MessagesSave):
    """覆盖保存会话全部消息"""
    sessions = _read()
    for s in sessions:
        if s["id"] == session_id:
            s["messages"] = [m.model_dump() for m in data.messages]
            # 自动以第一条用户消息截取标题
            if s["title"] == "新对话":
                user_msgs = [m for m in s["messages"] if m["role"] == "user"]
                if user_msgs:
                    s["title"] = user_msgs[0]["content"][:30]
            s["updated_at"] = datetime.now(timezone.utc).isoformat()
            _write(sessions)
            return {"status": "ok"}
    raise HTTPException(404, "会话不存在")
