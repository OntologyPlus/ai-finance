from __future__ import annotations

from functools import wraps
from typing import Any, Callable, Dict, Optional

from fastapi import HTTPException, Request
from loguru import logger

from ontology.permissions import OntologyPermissionEngine, ObjectType, RoleType


_permission_engine = OntologyPermissionEngine()


def get_role_from_request(request: Request) -> str:
    role = request.headers.get("X-User-Role", "")
    if not role:
        role = request.query_params.get("role_type", "员工")
    return role


def get_user_center_from_request(request: Request) -> Optional[str]:
    return request.headers.get("X-User-Center", None)


def get_user_dept_from_request(request: Request) -> Optional[str]:
    return request.headers.get("X-User-Department", None)


def get_user_id_from_request(request: Request) -> Optional[str]:
    return request.headers.get("X-User-ID", None)


def require_permission(object_type: str, min_scope: str = "own"):
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, request: Request = None, **kwargs):
            if request is None:
                for arg in args:
                    if isinstance(arg, Request):
                        request = arg
                        break
            if request is None:
                return await func(*args, **kwargs)

            role_type = get_role_from_request(request)
            scope_info = _permission_engine.get_data_scope(role_type)
            scope_level = scope_info["scope"]

            scope_hierarchy = {"all": 4, "center": 3, "department": 2, "own": 1, "l1_b6": 2}
            user_level = scope_hierarchy.get(scope_level, 1)
            required_level = scope_hierarchy.get(min_scope, 1)

            if user_level < required_level:
                raise HTTPException(
                    status_code=403,
                    detail=f"权限不足: 角色'{role_type}'的数据范围为'{scope_info['description']}'，需要'{min_scope}'级别权限",
                )

            return await func(*args, request=request, **kwargs)
        return wrapper
    return decorator


def filter_response_fields(
    role_type: str, object_type: str, data: Dict[str, Any]
) -> Dict[str, Any]:
    return _permission_engine.filter_object_fields(role_type, object_type, data)


def check_data_scope(
    role_type: str,
    user_center_id: Optional[str],
    user_department_id: Optional[str],
    user_employee_id: Optional[str],
    data_center_id: Optional[str],
    data_department_id: Optional[str],
    data_employee_id: Optional[str],
) -> bool:
    return _permission_engine.is_data_in_scope(
        role_type=role_type,
        user_center_id=user_center_id,
        user_department_id=user_department_id,
        user_employee_id=user_employee_id,
        data_center_id=data_center_id,
        data_department_id=data_department_id,
        data_employee_id=data_employee_id,
    )
