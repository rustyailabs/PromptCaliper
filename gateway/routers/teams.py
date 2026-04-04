from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from gateway.db.session import get_db
from gateway.dependencies import get_current_user, require_superadmin
from gateway.models.team import Team
from gateway.schemas.team import TeamCreate, TeamResponse, TeamUpdate

router = APIRouter(dependencies=[Depends(get_current_user)])


@router.get("", response_model=list[TeamResponse])
async def list_teams(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Team).order_by(Team.name))
    return result.scalars().all()


@router.post("", response_model=TeamResponse, status_code=status.HTTP_201_CREATED,
             dependencies=[Depends(require_superadmin)])
async def create_team(body: TeamCreate, db: AsyncSession = Depends(get_db)):
    team = Team(**body.model_dump())
    db.add(team)
    await db.flush()
    await db.refresh(team)
    return team


@router.get("/{team_id}", response_model=TeamResponse)
async def get_team(team_id: int, db: AsyncSession = Depends(get_db)):
    team = await db.get(Team, team_id)
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")
    return team


@router.patch("/{team_id}", response_model=TeamResponse,
              dependencies=[Depends(require_superadmin)])
async def update_team(team_id: int, body: TeamUpdate, db: AsyncSession = Depends(get_db)):
    team = await db.get(Team, team_id)
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(team, field, value)
    await db.flush()
    return team


@router.delete("/{team_id}", status_code=status.HTTP_204_NO_CONTENT,
               dependencies=[Depends(require_superadmin)])
async def delete_team(team_id: int, db: AsyncSession = Depends(get_db)):
    team = await db.get(Team, team_id)
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")
    await db.delete(team)
