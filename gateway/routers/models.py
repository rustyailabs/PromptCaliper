from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from gateway.db.session import get_db
from gateway.dependencies import get_current_user, get_litellm_service, require_superadmin
from gateway.models.model_config import ModelConfig
from gateway.schemas.model_config import ModelConfigCreate, ModelConfigResponse, ModelConfigUpdate

router = APIRouter(dependencies=[Depends(get_current_user)])


@router.get("", response_model=list[ModelConfigResponse])
async def list_models(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(ModelConfig).order_by(ModelConfig.display_name))
    return result.scalars().all()


@router.post("", response_model=ModelConfigResponse, status_code=status.HTTP_201_CREATED,
             dependencies=[Depends(require_superadmin)])
async def create_model(
    body: ModelConfigCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    litellm_service=Depends(get_litellm_service),
):
    model = ModelConfig(**body.model_dump())
    db.add(model)
    await db.flush()
    await db.refresh(model)
    await _reload_router(db, litellm_service)
    return model


@router.get("/{model_id}", response_model=ModelConfigResponse)
async def get_model(model_id: int, db: AsyncSession = Depends(get_db)):
    model = await db.get(ModelConfig, model_id)
    if not model:
        raise HTTPException(status_code=404, detail="Model not found")
    return model


@router.patch("/{model_id}", response_model=ModelConfigResponse,
              dependencies=[Depends(require_superadmin)])
async def update_model(
    model_id: int,
    body: ModelConfigUpdate,
    db: AsyncSession = Depends(get_db),
    litellm_service=Depends(get_litellm_service),
):
    model = await db.get(ModelConfig, model_id)
    if not model:
        raise HTTPException(status_code=404, detail="Model not found")
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(model, field, value)
    await db.flush()
    await _reload_router(db, litellm_service)
    return model


@router.delete("/{model_id}", status_code=status.HTTP_204_NO_CONTENT,
               dependencies=[Depends(require_superadmin)])
async def delete_model(
    model_id: int,
    db: AsyncSession = Depends(get_db),
    litellm_service=Depends(get_litellm_service),
):
    model = await db.get(ModelConfig, model_id)
    if not model:
        raise HTTPException(status_code=404, detail="Model not found")
    await db.delete(model)
    await db.flush()
    await _reload_router(db, litellm_service)


async def _reload_router(db: AsyncSession, litellm_service) -> None:
    result = await db.execute(select(ModelConfig).where(ModelConfig.is_active == True))
    model_configs = result.scalars().all()
    litellm_service.reinitialize(model_configs)
