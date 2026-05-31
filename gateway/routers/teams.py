from fastapi import APIRouter, Depends, HTTPException, status

from gateway.db.session import get_db
from gateway.dependencies import get_current_user, require_superadmin
from gateway.firestore_store import FirestoreStore
from gateway.schemas.team import TeamCreate, TeamResponse, TeamUpdate

router = APIRouter(dependencies=[Depends(get_current_user)])


@router.get("", response_model=list[TeamResponse])
def list_teams(db: FirestoreStore = Depends(get_db)):
    return db.list("teams", order_by="name")


@router.post("", response_model=TeamResponse, status_code=status.HTTP_201_CREATED,
             dependencies=[Depends(require_superadmin)])
async def create_team(body: TeamCreate, db: FirestoreStore = Depends(get_db)):
    return db.create("teams", {**body.model_dump(), "is_active": True})


@router.get("/{team_id}", response_model=TeamResponse)
async def get_team(team_id: int, db: FirestoreStore = Depends(get_db)):
    team = db.get("teams", team_id)
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")
    return team


@router.patch("/{team_id}", response_model=TeamResponse,
              dependencies=[Depends(require_superadmin)])
async def update_team(team_id: int, body: TeamUpdate, db: FirestoreStore = Depends(get_db)):
    team = db.get("teams", team_id)
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(team, field, value)
    return db.save(team)


@router.delete("/{team_id}", status_code=status.HTTP_204_NO_CONTENT,
               dependencies=[Depends(require_superadmin)])
async def delete_team(team_id: int, db: FirestoreStore = Depends(get_db)):
    if not db.get("teams", team_id):
        raise HTTPException(status_code=404, detail="Team not found")
    db.delete("teams", team_id)
