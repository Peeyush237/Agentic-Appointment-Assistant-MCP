from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    role: str = Field(default="patient", pattern="^(patient|doctor)$")
    message: str
    session_id: str | None = None


class ChatResponse(BaseModel):
    session_id: str
    response: str
    tool_trace: list[dict]


class HealthResponse(BaseModel):
    status: str
