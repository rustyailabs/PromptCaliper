from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from gateway.db.session import get_db
from gateway.dependencies import get_current_user, require_superadmin
from gateway.models.guardrail_config import GuardrailConfig
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
async def list_guardrails(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(GuardrailConfig).order_by(GuardrailConfig.created_at.desc()))
    return result.scalars().all()


@router.post("", response_model=GuardrailResponse, status_code=status.HTTP_201_CREATED,
             dependencies=[Depends(require_superadmin)])
async def create_guardrail(body: GuardrailCreate, db: AsyncSession = Depends(get_db)):
    g = GuardrailConfig(**body.model_dump())
    db.add(g)
    await db.flush()
    await db.refresh(g)
    return g


@router.patch("/{guardrail_id}", response_model=GuardrailResponse,
              dependencies=[Depends(require_superadmin)])
async def update_guardrail(guardrail_id: int, body: GuardrailUpdate, db: AsyncSession = Depends(get_db)):
    g = await db.get(GuardrailConfig, guardrail_id)
    if not g:
        raise HTTPException(status_code=404, detail="Guardrail not found")
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(g, field, value)
    await db.flush()
    return g


@router.delete("/{guardrail_id}", status_code=status.HTTP_204_NO_CONTENT,
               dependencies=[Depends(require_superadmin)])
async def delete_guardrail(guardrail_id: int, db: AsyncSession = Depends(get_db)):
    g = await db.get(GuardrailConfig, guardrail_id)
    if not g:
        raise HTTPException(status_code=404, detail="Guardrail not found")
    await db.delete(g)


@router.post("/test", response_model=GuardrailTestResponse)
async def test_guardrail(body: GuardrailTestRequest, db: AsyncSession = Depends(get_db)):
    try:
        processed, triggered, triggered_by = await apply_input_guardrails(body.messages, db)
        # Also run output guardrails on the concatenated input text (for testing only)
        input_text = " ".join(m.get("content", "") for m in body.messages if isinstance(m, dict))
        _, out_triggered, out_triggered_by = await apply_output_guardrails(input_text, db)
        all_triggered_by = list(dict.fromkeys(triggered_by + out_triggered_by))  # deduplicated
        return GuardrailTestResponse(
            triggered=triggered or out_triggered,
            triggered_by=all_triggered_by,
            processed_messages=processed,
        )
    except HTTPException as exc:
        return GuardrailTestResponse(
            triggered=True,
            triggered_by=[exc.detail],
            processed_messages=body.messages,
        )
