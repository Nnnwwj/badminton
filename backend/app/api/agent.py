from fastapi import APIRouter, HTTPException, status

from app.dependencies import (
    CurrentTime,
    CurrentUser,
    DatabaseSession,
    DeepSeekClientDependency,
)
from app.schemas import AgentChatRequest, AgentReply
from app.services.agent import AgentRunError, run_agent


router = APIRouter(prefix="/api/agent", tags=["agent"])


@router.post("/chat", response_model=AgentReply)
def chat(
    payload: AgentChatRequest,
    db: DatabaseSession,
    current_user: CurrentUser,
    client: DeepSeekClientDependency,
    now: CurrentTime,
) -> AgentReply:
    try:
        return run_agent(db, client, current_user, payload.message, now)
    except AgentRunError as error:
        status_code = (
            status.HTTP_503_SERVICE_UNAVAILABLE
            if error.code == "agent_unavailable"
            else status.HTTP_502_BAD_GATEWAY
        )
        messages = {
            "agent_unavailable": "推荐服务暂时不可用，请稍后重试",
            "invalid_model_output": "推荐结果无效，请重试",
            "agent_loop_limit": "推荐步骤过多，请缩小查询条件后重试",
        }
        raise HTTPException(
            status_code=status_code,
            detail={
                "code": error.code,
                "message": messages.get(error.code, "推荐失败，请重试"),
            },
        ) from None
