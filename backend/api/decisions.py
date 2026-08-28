"""Decision Intelligence APIs: fetch, chain, precedents, expense explain."""
from fastapi import APIRouter, HTTPException

from models.schemas import APIResponse
from ontology.decision_recorder import get_decision_recorder

router = APIRouter()


@router.get("/decisions/explain/expense/{expense_id}", response_model=APIResponse)
async def explain_expense_decision(expense_id: str):
    payload = await get_decision_recorder().explain_expense(expense_id)
    return APIResponse(success=True, data=payload)


@router.get("/decisions/{decision_id}", response_model=APIResponse)
async def get_decision(decision_id: str):
    rec = get_decision_recorder().get(decision_id)
    if rec is None:
        raise HTTPException(status_code=404, detail=f"Decision {decision_id} not found")
    return APIResponse(success=True, data=rec.model_dump(mode="json"))


@router.get("/decisions/{decision_id}/chain", response_model=APIResponse)
async def get_decision_chain(decision_id: str):
    payload = await get_decision_recorder().trace_decision_chain(decision_id)
    if payload.get("decision") is None and not payload.get("hops"):
        raise HTTPException(status_code=404, detail=f"Decision {decision_id} not found")
    return APIResponse(success=True, data=payload)


@router.post("/decisions/search", response_model=APIResponse)
async def search_decisions(body: dict):
    category = (body.get("category") or "").strip()
    if not category:
        raise HTTPException(status_code=400, detail="category is required")
    applied = body.get("applied_rule_ids") or []
    limit = int(body.get("limit") or 10)
    matches = get_decision_recorder().find_precedents(category, list(applied), limit=limit)
    return APIResponse(
        success=True,
        data={"matches": [r.model_dump(mode="json") for r in matches], "count": len(matches)},
    )
