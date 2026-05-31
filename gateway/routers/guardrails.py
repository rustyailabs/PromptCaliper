from fastapi import APIRouter, Depends, HTTPException, status

from gateway.db.session import get_db
from gateway.dependencies import get_current_user, require_superadmin
from gateway.firestore_store import FirestoreStore
from gateway.schemas.guardrail import (
    GuardrailCreate,
    GuardrailResponse,
    GuardrailTestRequest,
    GuardrailTestResponse,
    GuardrailUpdate,
)
from gateway.services.guardrail_service import apply_input_guardrails, apply_output_guardrails

router = APIRouter(dependencies=[Depends(get_current_user)])


@router.get("", response_model=list[GuardrailResponse])
def list_guardrails(db: FirestoreStore = Depends(get_db)):
    return db.list("guardrail_configs", order_by="created_at", desc=True)


@router.post("", response_model=GuardrailResponse, status_code=status.HTTP_201_CREATED,
             dependencies=[Depends(require_superadmin)])
async def create_guardrail(body: GuardrailCreate, db: FirestoreStore = Depends(get_db)):
    return db.create("guardrail_configs", {**body.model_dump(), "is_active": True})


@router.patch("/{guardrail_id}", response_model=GuardrailResponse,
              dependencies=[Depends(require_superadmin)])
async def update_guardrail(guardrail_id: int, body: GuardrailUpdate, db: FirestoreStore = Depends(get_db)):
    guardrail = db.get("guardrail_configs", guardrail_id)
    if not guardrail:
        raise HTTPException(status_code=404, detail="Guardrail not found")
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(guardrail, field, value)
    return db.save(guardrail)


@router.delete("/{guardrail_id}", status_code=status.HTTP_204_NO_CONTENT,
               dependencies=[Depends(require_superadmin)])
async def delete_guardrail(guardrail_id: int, db: FirestoreStore = Depends(get_db)):
    if not db.get("guardrail_configs", guardrail_id):
        raise HTTPException(status_code=404, detail="Guardrail not found")
    db.delete("guardrail_configs", guardrail_id)


@router.post("/test", response_model=GuardrailTestResponse)
async def test_guardrail(body: GuardrailTestRequest, db: FirestoreStore = Depends(get_db)):
    try:
        processed, triggered, triggered_by = await apply_input_guardrails(body.messages, db)
        input_text = " ".join(m.get("content", "") for m in body.messages if isinstance(m, dict))
        _, out_triggered, out_triggered_by = await apply_output_guardrails(input_text, db)
        return GuardrailTestResponse(
            triggered=triggered or out_triggered,
            triggered_by=list(dict.fromkeys(triggered_by + out_triggered_by)),
            processed_messages=processed,
        )
    except HTTPException as exc:
        return GuardrailTestResponse(triggered=True, triggered_by=[exc.detail], processed_messages=body.messages)
