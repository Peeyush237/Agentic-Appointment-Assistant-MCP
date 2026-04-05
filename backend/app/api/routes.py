from fastapi import APIRouter

from app.api.schemas import ChatRequest, ChatResponse, HealthResponse
from app.core.agent import agent

router = APIRouter(prefix="/api", tags=["api"])


@router.get("/health", response_model=HealthResponse)
async def health_check():
    return HealthResponse(status="ok")


@router.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest):
    result = await agent.run(role=req.role, user_message=req.message, session_id=req.session_id)
    return ChatResponse(session_id=result["session_id"], response=result["answer"], tool_trace=result["tool_trace"])
