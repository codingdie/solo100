"""REST router for AgentConfig CRUD operations."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.agent_config import AgentConfig
from app.schemas.agent import (
    AgentConfigCreate,
    AgentConfigListResponse,
    AgentConfigResponse,
    AgentConfigUpdate,
)

router = APIRouter(prefix="/api/v1/agents", tags=["agents"])


@router.get("", response_model=AgentConfigListResponse)
async def list_agents(db: AsyncSession = Depends(get_db)) -> AgentConfigListResponse:
    """Return all agent configurations."""
    result = await db.execute(
        select(AgentConfig).order_by(AgentConfig.created_at.desc()),
    )
    items = result.scalars().all()
    return AgentConfigListResponse(
        items=[AgentConfigResponse.model_validate(a) for a in items],
        total=len(items),
    )


@router.post(
    "",
    response_model=AgentConfigResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_agent(
    payload: AgentConfigCreate,
    db: AsyncSession = Depends(get_db),
) -> AgentConfigResponse:
    """Create a new agent configuration."""
    if payload.is_default:
        result = await db.execute(
            select(AgentConfig).where(AgentConfig.is_default == 1),
        )
        for agent in result.scalars():
            agent.is_default = 0

    agent = AgentConfig(
        name=payload.name,
        type=payload.type,
        api_key_env=payload.api_key_env,
        is_default=1 if payload.is_default else 0,
    )
    db.add(agent)
    await db.flush()
    await db.refresh(agent)
    return AgentConfigResponse.model_validate(agent)


@router.put("/{agent_id}", response_model=AgentConfigResponse)
async def update_agent(
    agent_id: str,
    payload: AgentConfigUpdate,
    db: AsyncSession = Depends(get_db),
) -> AgentConfigResponse:
    """Update an agent configuration (partial update)."""
    result = await db.execute(
        select(AgentConfig).where(AgentConfig.id == agent_id),
    )
    agent = result.scalar_one_or_none()
    if agent is None:
        raise HTTPException(status_code=404, detail="Agent not found")

    update_data = payload.model_dump(exclude_unset=True)
    if "is_default" in update_data and update_data["is_default"]:
        other_result = await db.execute(
            select(AgentConfig).where(
                AgentConfig.is_default == 1,
                AgentConfig.id != agent_id,
            ),
        )
        for other in other_result.scalars():
            other.is_default = 0
        update_data["is_default"] = 1
    elif "is_default" in update_data:
        update_data["is_default"] = 0

    for field, value in update_data.items():
        setattr(agent, field, value)

    await db.flush()
    await db.refresh(agent)
    return AgentConfigResponse.model_validate(agent)
