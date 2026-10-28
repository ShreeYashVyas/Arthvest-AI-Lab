"""AI research-agent endpoints."""

import logging

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, field_validator

from app.services import research_agents

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/agents", tags=["AI research agents"])


class ResearchRequest(BaseModel):
    """Bounded user request for a research brief."""

    question: str = Field(min_length=4, max_length=600)

    @field_validator("question", mode="before")
    @classmethod
    def trim_question(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value


@router.get("/status", summary="Check AI research-agent configuration")
def get_research_agent_status() -> dict[str, object]:
    """Report readiness without disclosing the configured API key."""
    return research_agents.get_agent_status()


@router.post("/research", summary="Run the Arthvest multi-agent research workflow")
async def create_research_brief(request: ResearchRequest) -> dict[str, object]:
    """Collect source context, run specialist agents, and synthesize a research brief."""
    status = research_agents.get_agent_status()
    if not status["configured"]:
        raise HTTPException(
            status_code=503,
            detail=str(status["note"]),
        )

    try:
        return await research_agents.run_research(request.question.strip())
    except Exception as exc:
        logger.warning("AI research workflow failed (%s)", type(exc).__name__)
        raise HTTPException(
            status_code=502,
            detail="The AI research workflow could not complete. Check the backend log and API configuration.",
        ) from exc
