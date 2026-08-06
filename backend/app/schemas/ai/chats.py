from typing import List

from pydantic import BaseModel


class ChatMessage(BaseModel):
    role: str
    content: str
    patient_context: dict | None = None


class ChatRequest(BaseModel):
    message: str
    conversation_history: List[ChatMessage] = []
    patient_context: dict | None = None


class ChatResponse(BaseModel):
    response: str
    patient_context: dict | None = None