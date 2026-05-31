from fastapi import APIRouter, Depends, HTTPException, status

from gateway.db.session import get_db
from gateway.dependencies import get_current_user, get_litellm_service, require_superadmin
from gateway.firestore_store import FirestoreStore
from gateway.schemas.model_config import ModelConfigCreate, ModelConfigResponse, ModelConfigUpdate
from gateway.services.litellm_service import active_model_configs

router = APIRouter(dependencies=[Depends(get_current_user)])


@router.get("", response_model=list[ModelConfigResponse])
def list_models(db: FirestoreStore = Depends(get_db)):
    return db.list("model_configs", order_by="display_name")


@router.post("", response_model=ModelConfigResponse, status_code=status.HTTP_201_CREATED,
             dependencies=[Depends(require_superadmin)])
async def create_model(
    body: ModelConfigCreate,
    db: FirestoreStore = Depends(get_db),
    litellm_service=Depends(get_litellm_service),
):
    model = db.create("model_configs", {
        **body.model_dump(),
        "avg_latency_ms": None,
        "is_active": True,
        "status": "active",
    })
    await _reload_router(db, litellm_service)
    return model


@router.get("/{model_id}", response_model=ModelConfigResponse)
async def get_model(model_id: int, db: FirestoreStore = Depends(get_db)):
    model = db.get("model_configs", model_id)
    if not model:
        raise HTTPException(status_code=404, detail="Model not found")
    return model


@router.patch("/{model_id}", response_model=ModelConfigResponse,
              dependencies=[Depends(require_superadmin)])
async def update_model(
    model_id: int,
    body: ModelConfigUpdate,
    db: FirestoreStore = Depends(get_db),
    litellm_service=Depends(get_litellm_service),
):
    model = db.get("model_configs", model_id)
    if not model:
        raise HTTPException(status_code=404, detail="Model not found")
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(model, field, value)
    db.save(model)
    await _reload_router(db, litellm_service)
    return model


@router.delete("/{model_id}", status_code=status.HTTP_204_NO_CONTENT,
               dependencies=[Depends(require_superadmin)])
async def delete_model(
    model_id: int,
    db: FirestoreStore = Depends(get_db),
    litellm_service=Depends(get_litellm_service),
):
    if not db.get("model_configs", model_id):
        raise HTTPException(status_code=404, detail="Model not found")
    db.delete("model_configs", model_id)
    await _reload_router(db, litellm_service)


async def _reload_router(db: FirestoreStore, litellm_service) -> None:
    litellm_service.reinitialize(active_model_configs(db))
