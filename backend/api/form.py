import uuid
from typing import Optional
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from models.database import get_db
from models.schemas import APIResponse, APIPageResponse
from models.form import FormTemplate, FormSubmission

router = APIRouter()


@router.get("/forms/templates", response_model=APIResponse)
async def list_form_templates(
    category: Optional[str] = Query(None, description="表单分类: budget/expense/alert/analysis/pdca/report/cycle"),
    db: AsyncSession = Depends(get_db),
):
    try:
        stmt = select(FormTemplate)
        if category:
            stmt = stmt.where(FormTemplate.category == category)
        result = await db.execute(stmt)
        templates = result.scalars().all()
        data = [{c: getattr(r, c) for c in r.__table__.columns.keys()} for r in templates]
        return APIResponse(success=True, data=data)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/forms/templates/{form_code}", response_model=APIResponse)
async def get_form_template(
    form_code: str,
    db: AsyncSession = Depends(get_db),
):
    try:
        stmt = select(FormTemplate).where(FormTemplate.form_code == form_code)
        result = await db.execute(stmt)
        template = result.scalar_one_or_none()
        if template is None:
            raise HTTPException(status_code=404, detail=f"Form template {form_code} not found")
        data = {c: getattr(template, c) for c in template.__table__.columns.keys()}
        return APIResponse(success=True, data=data)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/forms/templates", response_model=APIResponse)
async def create_form_template(
    template_data: dict,
    db: AsyncSession = Depends(get_db),
):
    try:
        form_code = template_data.get("form_code")
        if not form_code:
            raise HTTPException(status_code=400, detail="form_code is required")
        stmt = select(FormTemplate).where(FormTemplate.form_code == form_code)
        result = await db.execute(stmt)
        existing = result.scalar_one_or_none()
        if existing:
            raise HTTPException(status_code=409, detail=f"Form template {form_code} already exists")
        template_id = template_data.get("id") or str(uuid.uuid4())[:64]
        template_data["id"] = template_id
        template = FormTemplate(**template_data)
        db.add(template)
        await db.flush()
        data = {c: getattr(template, c) for c in template.__table__.columns.keys()}
        return APIResponse(success=True, message="Form template created", data=data)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/forms/templates/{form_code}", response_model=APIResponse)
async def update_form_template(
    form_code: str,
    update_data: dict,
    db: AsyncSession = Depends(get_db),
):
    try:
        stmt = select(FormTemplate).where(FormTemplate.form_code == form_code)
        result = await db.execute(stmt)
        template = result.scalar_one_or_none()
        if template is None:
            raise HTTPException(status_code=404, detail=f"Form template {form_code} not found")
        for key, value in update_data.items():
            if hasattr(template, key) and key not in ("id", "form_code"):
                setattr(template, key, value)
        await db.flush()
        data = {c: getattr(template, c) for c in template.__table__.columns.keys()}
        return APIResponse(success=True, message="Form template updated", data=data)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/forms/submissions", response_model=APIResponse)
async def submit_form(
    submission_data: dict,
    db: AsyncSession = Depends(get_db),
):
    try:
        form_code = submission_data.get("form_code")
        if not form_code:
            raise HTTPException(status_code=400, detail="form_code is required")
        submitter_id = submission_data.get("submitter_id")
        if not submitter_id:
            raise HTTPException(status_code=400, detail="submitter_id is required")
        submission_id = submission_data.get("submission_id") or f"SUB-{str(uuid.uuid4())[:8]}"
        submission_data["id"] = submission_data.get("id") or str(uuid.uuid4())[:64]
        submission_data["submission_id"] = submission_id
        submission = FormSubmission(**submission_data)
        db.add(submission)
        await db.flush()
        data = {c: getattr(submission, c) for c in submission.__table__.columns.keys()}
        return APIResponse(success=True, message="Form submitted", data=data)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/forms/submissions", response_model=APIResponse)
async def list_form_submissions(
    form_code: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    org_id: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    try:
        conditions = []
        if form_code:
            conditions.append(FormSubmission.form_code == form_code)
        if status:
            conditions.append(FormSubmission.status == status)
        if org_id:
            conditions.append(FormSubmission.org_id == org_id)
        stmt = select(FormSubmission).where(and_(*conditions)) if conditions else select(FormSubmission)
        result = await db.execute(stmt)
        submissions = result.scalars().all()
        data = [{c: getattr(r, c) for c in r.__table__.columns.keys()} for r in submissions]
        return APIResponse(success=True, data=data)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/forms/submissions/{submission_id}", response_model=APIResponse)
async def get_form_submission(
    submission_id: str,
    db: AsyncSession = Depends(get_db),
):
    try:
        stmt = select(FormSubmission).where(FormSubmission.submission_id == submission_id)
        result = await db.execute(stmt)
        submission = result.scalar_one_or_none()
        if submission is None:
            raise HTTPException(status_code=404, detail=f"Form submission {submission_id} not found")
        data = {c: getattr(submission, c) for c in submission.__table__.columns.keys()}
        return APIResponse(success=True, data=data)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/forms/submissions/{submission_id}/review", response_model=APIResponse)
async def review_form_submission(
    submission_id: str,
    body: dict,
    db: AsyncSession = Depends(get_db),
):
    try:
        stmt = select(FormSubmission).where(FormSubmission.submission_id == submission_id)
        result = await db.execute(stmt)
        submission = result.scalar_one_or_none()
        if submission is None:
            raise HTTPException(status_code=404, detail=f"Form submission {submission_id} not found")
        action = body.get("action", "通过")
        submission.status = "已审核" if action == "通过" else "已驳回"
        submission.reviewer_id = body.get("reviewer_id", "")
        submission.review_comment = body.get("comment", "")
        submission.reviewed_at = datetime.now()
        await db.flush()
        data = {c: getattr(submission, c) for c in submission.__table__.columns.keys()}
        return APIResponse(success=True, message="Form submission reviewed", data=data)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
