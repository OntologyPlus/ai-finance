import json
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from models.database import get_db
from models.schemas import APIResponse
from models.organization import Department, Role, Employee
from models.config import settings


router = APIRouter()


# ── Audit log in-memory store ──
_AUDIT_LOG: list[dict] = []


def _add_audit_log(user: str, action: str, target: str, details: str = ""):
    from datetime import datetime
    _AUDIT_LOG.append({
        "timestamp": datetime.now().isoformat(),
        "user": user,
        "action": action,
        "target": target,
        "details": details,
    })
    # Keep last 200 entries
    if len(_AUDIT_LOG) > 200:
        _AUDIT_LOG.pop(0)


@router.get("/settings", response_model=APIResponse)
async def get_settings():
    try:
        data = {
            "llm_model": settings.LLM_MODEL,
            "allowed_origins": settings.allowed_origins_list,
        }
        return APIResponse(success=True, data=data)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/settings", response_model=APIResponse)
async def update_settings(
    body: dict,
):
    try:
        updatable_fields = ["LLM_MODEL"]
        updated = {}
        for field in updatable_fields:
            if field in body:
                setattr(settings, field, body[field])
                updated[field] = body[field]

        return APIResponse(success=True, message="Settings updated", data=updated)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/settings/organization", response_model=APIResponse)
async def get_organization_structure(
    db: AsyncSession = Depends(get_db),
):
    try:
        stmt_dept = select(Department).where(Department.is_active.is_(True))
        result_dept = await db.execute(stmt_dept)
        departments = result_dept.scalars().all()

        dept_data = [{c: getattr(r, c) for c in r.__table__.columns.keys()} for r in departments]

        stmt_emp = select(Employee).where(Employee.is_active.is_(True))
        result_emp = await db.execute(stmt_emp)
        employees = result_emp.scalars().all()

        emp_data = [{c: getattr(r, c) for c in r.__table__.columns.keys()} for r in employees]

        org_tree = {}
        for dept in departments:
            center_id = dept.center_id or "unknown"
            if center_id not in org_tree:
                org_tree[center_id] = {"departments": [], "employees": []}
            org_tree[center_id]["departments"].append({
                "dept_id": dept.dept_id,
                "dept_name": dept.dept_name,
            })

        for emp in employees:
            center_id = emp.center_id or "unknown"
            if center_id in org_tree:
                org_tree[center_id]["employees"].append({
                    "employee_id": emp.employee_id,
                    "employee_name": emp.employee_name,
                    "dept_id": emp.dept_id,
                })

        data = {
            "departments": dept_data,
            "employees": emp_data,
            "org_tree": org_tree,
        }

        return APIResponse(success=True, data=data)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/settings/roles", response_model=APIResponse)
async def get_roles(
    db: AsyncSession = Depends(get_db),
):
    try:
        stmt = select(Role)
        result = await db.execute(stmt)
        roles = result.scalars().all()

        data = [{c: getattr(r, c) for c in r.__table__.columns.keys()} for r in roles]
        return APIResponse(success=True, data=data)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Department CRUD ──


@router.post("/settings/departments", response_model=APIResponse)
async def create_department(
    body: dict,
    db: AsyncSession = Depends(get_db),
):
    dept_id = body.get("dept_id")
    dept_name = body.get("dept_name")
    if not dept_id or not dept_name:
        raise HTTPException(status_code=400, detail="dept_id and dept_name are required")

    try:
        existing = await db.get(Department, dept_id)
        if existing:
            raise HTTPException(status_code=409, detail=f"Department {dept_id} already exists")

        dept = Department(
            dept_id=dept_id,
            dept_name=dept_name,
            center_id=body.get("center_id"),
            parent_dept_id=body.get("parent_dept_id"),
            legal_entity_id=body.get("legal_entity_id"),
            is_active=True,
        )
        db.add(dept)
        await db.flush()

        data = {c: getattr(dept, c) for c in dept.__table__.columns.keys()}
        _add_audit_log("admin", "创建部门", dept_id, f"名称: {dept_name}")
        return APIResponse(success=True, message="Department created", data=data)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/settings/departments/{dept_id}", response_model=APIResponse)
async def update_department(
    dept_id: str,
    body: dict,
    db: AsyncSession = Depends(get_db),
):
    try:
        dept = await db.get(Department, dept_id)
        if dept is None:
            raise HTTPException(status_code=404, detail=f"Department {dept_id} not found")

        for key, value in body.items():
            if hasattr(dept, key) and key != "dept_id":
                setattr(dept, key, value)

        await db.flush()
        data = {c: getattr(dept, c) for c in dept.__table__.columns.keys()}
        _add_audit_log("admin", "更新部门", dept_id, json.dumps(body, ensure_ascii=False))
        return APIResponse(success=True, message="Department updated", data=data)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/settings/departments/{dept_id}", response_model=APIResponse)
async def delete_department(
    dept_id: str,
    db: AsyncSession = Depends(get_db),
):
    try:
        dept = await db.get(Department, dept_id)
        if dept is None:
            raise HTTPException(status_code=404, detail=f"Department {dept_id} not found")

        dept.is_active = False
        await db.flush()
        _add_audit_log("admin", "删除部门", dept_id)
        return APIResponse(success=True, message="Department deleted")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Role permissions ──


@router.put("/settings/roles/{role_id}/permissions", response_model=APIResponse)
async def update_role_permissions(
    role_id: str,
    body: dict,
    db: AsyncSession = Depends(get_db),
):
    permissions = body.get("permissions", [])
    try:
        role = await db.get(Role, role_id)
        if role is None:
            raise HTTPException(status_code=404, detail=f"Role {role_id} not found")

        role.permissions = json.dumps(permissions, ensure_ascii=False)
        await db.flush()

        data = {c: getattr(role, c) for c in role.__table__.columns.keys()}
        _add_audit_log("admin", "更新角色权限", role_id, f"权限: {json.dumps(permissions, ensure_ascii=False)}")
        return APIResponse(success=True, message="Role permissions updated", data=data)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Audit log ──


@router.get("/settings/audit-log", response_model=APIResponse)
async def get_audit_log(
    limit: int = 50,
):
    entries = _AUDIT_LOG[-limit:]
    return APIResponse(success=True, data=entries)


# ── Alignment map configuration ──

DEFAULT_ALIGNMENT_MAP = {
    "创新研发": ["B2"],
    "全渠道商业化": ["B5", "B3"],
    "国际化": ["B5", "B3", "B9"],
}


# ── Caliber mapping configuration ──


@router.get("/settings/caliber-mappings", response_model=APIResponse)
async def get_caliber_mappings(
    db: AsyncSession = Depends(get_db),
):
    """获取口径映射配置列表"""
    try:
        from models.caliber import CaliberMapping
        stmt = select(CaliberMapping).order_by(CaliberMapping.sort_order)
        result = await db.execute(stmt)
        mappings = result.scalars().all()

        data = []
        for m in mappings:
            data.append({
                "mapping_id": m.mapping_id,
                "financial_code": m.financial_code,
                "financial_name": m.financial_name,
                "management_code": m.management_code,
                "management_name": m.management_name,
                "conversion_rule": m.conversion_rule,
                "adjustment_formula": m.adjustment_formula,
                "difference_note": m.difference_note,
                "sort_order": m.sort_order,
            })
        return APIResponse(success=True, data=data)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/settings/caliber-mappings", response_model=APIResponse)
async def update_caliber_mappings(
    body: dict,
    db: AsyncSession = Depends(get_db),
):
    """批量更新口径映射配置

    body.mappings: list of { mapping_id, adjustment_formula, ... }
    """
    mappings_data = body.get("mappings", [])
    if not isinstance(mappings_data, list):
        raise HTTPException(status_code=400, detail="mappings must be a list")

    try:
        from models.caliber import CaliberMapping
        updated = []
        for item in mappings_data:
            mapping_id = item.get("mapping_id")
            if not mapping_id:
                continue
            mapping = await db.get(CaliberMapping, mapping_id)
            if mapping is None:
                continue
            if "adjustment_formula" in item:
                mapping.adjustment_formula = item["adjustment_formula"]
            if "difference_note" in item:
                mapping.difference_note = item["difference_note"]
            if "management_name" in item:
                mapping.management_name = item["management_name"]
            if "conversion_rule" in item:
                mapping.conversion_rule = item["conversion_rule"]
            updated.append({
                "mapping_id": mapping.mapping_id,
                "adjustment_formula": mapping.adjustment_formula,
            })

        await db.flush()
        _add_audit_log("admin", "更新口径映射", "caliber_mappings", f"更新{len(updated)}条")
        return APIResponse(success=True, message=f"Updated {len(updated)} caliber mappings", data=updated)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Alert threshold configuration ──


@router.get("/settings/alert-thresholds", response_model=APIResponse)
async def get_alert_thresholds(
    db: AsyncSession = Depends(get_db),
):
    """获取预警阈值配置"""
    try:
        from models.ontology import OntologyRule
        threshold_rules = [
            {"rule_id": "ALERT-STRATEGIC-LOW-THRESHOLD", "default": 40, "name": "战略维度低执行率阈值(%)"},
            {"rule_id": "ALERT-STRATEGIC-HIGH-THRESHOLD", "default": 100, "name": "战略维度超执行率阈值(%)"},
        ]
        data = []
        for rule_def in threshold_rules:
            stmt = select(OntologyRule).where(
                and_(
                    OntologyRule.rule_id == rule_def["rule_id"],
                    OntologyRule.is_active.is_(True),
                )
            )
            result = await db.execute(stmt)
            rule = result.scalars().first()
            value = rule_def["default"]
            if rule and rule.result:
                try:
                    value = int(float(rule.result))
                except (ValueError, TypeError):
                    pass
            data.append({
                "rule_id": rule_def["rule_id"],
                "name": rule_def["name"],
                "value": value,
                "default": rule_def["default"],
            })
        return APIResponse(success=True, data=data)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/settings/alert-thresholds", response_model=APIResponse)
async def update_alert_thresholds(
    body: dict,
    db: AsyncSession = Depends(get_db),
):
    """更新预警阈值配置

    body.thresholds: list of { rule_id, value }
    """
    thresholds = body.get("thresholds", [])
    if not isinstance(thresholds, list):
        raise HTTPException(status_code=400, detail="thresholds must be a list")

    try:
        from models.ontology import OntologyRule
        updated = []
        for item in thresholds:
            rule_id = item.get("rule_id")
            value = item.get("value")
            if not rule_id or value is None:
                continue
            stmt = select(OntologyRule).where(
                and_(
                    OntologyRule.rule_id == rule_id,
                    OntologyRule.is_active.is_(True),
                )
            )
            result = await db.execute(stmt)
            rule = result.scalars().first()
            if rule:
                rule.result = str(value)
            else:
                rule = OntologyRule(
                    rule_id=rule_id,
                    rule_name=f"预警阈值: {rule_id}",
                    rule_type="alert_threshold",
                    condition="true",
                    result=str(value),
                    is_active=True,
                )
                db.add(rule)
            updated.append({"rule_id": rule_id, "value": value})

        await db.flush()
        _add_audit_log("admin", "更新预警阈值", "alert_thresholds", f"更新{len(updated)}条")
        return APIResponse(success=True, message=f"Updated {len(updated)} alert thresholds", data=updated)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Alignment map configuration ──


@router.get("/settings/alignment-map", response_model=APIResponse)
async def get_alignment_map(
    db: AsyncSession = Depends(get_db),
):
    """获取当前战略对齐映射配置"""
    try:
        from models.ontology import OntologyRule
        stmt = select(OntologyRule).where(
            OntologyRule.rule_type == "strategic_alignment_map",
            OntologyRule.is_active.is_(True),
        )
        result = await db.execute(stmt)
        db_rule = result.scalars().first()
        if db_rule and db_rule.result:
            alignment_map = json.loads(db_rule.result)
        else:
            alignment_map = DEFAULT_ALIGNMENT_MAP
        return APIResponse(success=True, data=alignment_map)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/settings/alignment-map", response_model=APIResponse)
async def update_alignment_map(
    body: dict,
    db: AsyncSession = Depends(get_db),
):
    """更新战略对齐映射配置（写入OntologyRule表）"""
    alignment_map = body.get("alignment_map")
    if not alignment_map or not isinstance(alignment_map, dict):
        raise HTTPException(status_code=400, detail="alignment_map must be a non-empty dict")
    try:
        from models.ontology import OntologyRule
        import uuid

        stmt = select(OntologyRule).where(
            OntologyRule.rule_type == "strategic_alignment_map",
            OntologyRule.is_active.is_(True),
        )
        result = await db.execute(stmt)
        db_rule = result.scalars().first()

        if db_rule:
            db_rule.result = json.dumps(alignment_map, ensure_ascii=False)
        else:
            db_rule = OntologyRule(
                rule_id=f"RULE-ALIGN-{uuid.uuid4().hex[:6].upper()}",
                rule_name="战略对齐映射配置",
                rule_type="strategic_alignment_map",
                condition="strategic_intent_l1 != null",
                result=json.dumps(alignment_map, ensure_ascii=False),
                is_active=True,
            )
            db.add(db_rule)

        await db.flush()
        _add_audit_log("admin", "更新对齐映射", "alignment_map", json.dumps(alignment_map, ensure_ascii=False))
        return APIResponse(success=True, message="Alignment map updated", data=alignment_map)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
