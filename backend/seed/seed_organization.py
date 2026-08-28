from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from models.organization import Department, Role, Employee


CENTERS = [
    {"dept_id": "C001", "dept_name": "津康中心", "center_id": "C001", "parent_dept_id": None, "legal_entity_id": "LE001", "is_active": True},
    {"dept_id": "C002", "dept_name": "华北中心", "center_id": "C002", "parent_dept_id": None, "legal_entity_id": "LE002", "is_active": True},
    {"dept_id": "C003", "dept_name": "华东中心", "center_id": "C003", "parent_dept_id": None, "legal_entity_id": "LE003", "is_active": True},
    {"dept_id": "C004", "dept_name": "华南中心", "center_id": "C004", "parent_dept_id": None, "legal_entity_id": "LE004", "is_active": True},
]

DEPARTMENTS = [
    {"dept_id": "D001", "dept_name": "津康中心-KA部", "center_id": "C001", "parent_dept_id": "C001", "legal_entity_id": "LE001", "is_active": True},
    {"dept_id": "D002", "dept_name": "津康中心-市场部", "center_id": "C001", "parent_dept_id": "C001", "legal_entity_id": "LE001", "is_active": True},
    {"dept_id": "D003", "dept_name": "津康中心-研发部", "center_id": "C001", "parent_dept_id": "C001", "legal_entity_id": "LE001", "is_active": True},
    {"dept_id": "D004", "dept_name": "华北中心-KA部", "center_id": "C002", "parent_dept_id": "C002", "legal_entity_id": "LE002", "is_active": True},
    {"dept_id": "D005", "dept_name": "华北中心-市场部", "center_id": "C002", "parent_dept_id": "C002", "legal_entity_id": "LE002", "is_active": True},
    {"dept_id": "D006", "dept_name": "华北中心-研发部", "center_id": "C002", "parent_dept_id": "C002", "legal_entity_id": "LE002", "is_active": True},
    {"dept_id": "D007", "dept_name": "华东中心-KA部", "center_id": "C003", "parent_dept_id": "C003", "legal_entity_id": "LE003", "is_active": True},
    {"dept_id": "D008", "dept_name": "华东中心-市场部", "center_id": "C003", "parent_dept_id": "C003", "legal_entity_id": "LE003", "is_active": True},
    {"dept_id": "D009", "dept_name": "华东中心-研发部", "center_id": "C003", "parent_dept_id": "C003", "legal_entity_id": "LE003", "is_active": True},
    {"dept_id": "D010", "dept_name": "华南中心-KA部", "center_id": "C004", "parent_dept_id": "C004", "legal_entity_id": "LE004", "is_active": True},
    {"dept_id": "D011", "dept_name": "华南中心-市场部", "center_id": "C004", "parent_dept_id": "C004", "legal_entity_id": "LE004", "is_active": True},
    {"dept_id": "D012", "dept_name": "华南中心-研发部", "center_id": "C004", "parent_dept_id": "C004", "legal_entity_id": "LE004", "is_active": True},
]

ROLES = [
    {"role_id": "R001", "role_name": "部门负责人", "role_type": "管理层", "permissions": '["approve_expense","view_budget","submit_expense","view_report"]', "description": "部门一级负责人，负责本部门预算执行和费用审批"},
    {"role_id": "R002", "role_name": "中心总经理", "role_type": "高管层", "permissions": '["approve_expense","view_budget","submit_expense","view_report","adjust_budget","approve_b2a"]', "description": "中心总经理，负责中心全面管理和高金额审批"},
    {"role_id": "R003", "role_name": "法人财务负责人", "role_type": "财务线", "permissions": '["approve_expense_legal","view_budget","view_report","audit_expense"]', "description": "法人架构线财务审批负责人"},
    {"role_id": "R004", "role_name": "法人或授权人", "role_type": "法人线", "permissions": '["approve_expense_legal","view_budget","view_report"]', "description": "法人或授权人，负责法人线最终审批"},
    {"role_id": "R005", "role_name": "财经BP", "role_type": "财务线", "permissions": '["confirm_alert","view_budget","view_report","write_off"]', "description": "财经BP，负责预警确认和预算核销"},
    {"role_id": "R006", "role_name": "财经经理", "role_type": "财务线", "permissions": '["view_budget","view_report","manage_write_off"]', "description": "财经经理，负责预算管理和核销管理"},
    {"role_id": "R007", "role_name": "部门经理", "role_type": "管理层", "permissions": '["submit_expense","view_budget","view_report"]', "description": "部门经理，可提交报销和查看预算报表"},
    {"role_id": "R008", "role_name": "普通员工", "role_type": "执行层", "permissions": '["submit_expense","view_own_report"]', "description": "普通员工，可提交报销和查看个人报表"},
]

EMPLOYEES = [
    {"employee_id": "EMP-001", "employee_name": "张津康", "dept_id": "D001", "center_id": "C001", "role_id": "R002", "email": "zhangjk@jinkang.com", "phone": "13800000001", "is_active": True},
    {"employee_id": "EMP-002", "employee_name": "李明", "dept_id": "D001", "center_id": "C001", "role_id": "R001", "email": "liming@jinkang.com", "phone": "13800000002", "is_active": True},
    {"employee_id": "EMP-003", "employee_name": "王芳", "dept_id": "D002", "center_id": "C001", "role_id": "R001", "email": "wangfang@jinkang.com", "phone": "13800000003", "is_active": True},
    {"employee_id": "EMP-004", "employee_name": "赵强", "dept_id": "D003", "center_id": "C001", "role_id": "R001", "email": "zhaoqiang@jinkang.com", "phone": "13800000004", "is_active": True},
    {"employee_id": "EMP-005", "employee_name": "刘华北", "dept_id": "D004", "center_id": "C002", "role_id": "R002", "email": "liuhuabei@jinkang.com", "phone": "13800000005", "is_active": True},
    {"employee_id": "EMP-006", "employee_name": "陈刚", "dept_id": "D004", "center_id": "C002", "role_id": "R001", "email": "chengang@jinkang.com", "phone": "13800000006", "is_active": True},
    {"employee_id": "EMP-007", "employee_name": "孙丽", "dept_id": "D005", "center_id": "C002", "role_id": "R007", "email": "sunli@jinkang.com", "phone": "13800000007", "is_active": True},
    {"employee_id": "EMP-008", "employee_name": "周伟", "dept_id": "D006", "center_id": "C002", "role_id": "R001", "email": "zhouwei@jinkang.com", "phone": "13800000008", "is_active": True},
    {"employee_id": "EMP-009", "employee_name": "吴华东", "dept_id": "D007", "center_id": "C003", "role_id": "R002", "email": "wuhuadong@jinkang.com", "phone": "13800000009", "is_active": True},
    {"employee_id": "EMP-010", "employee_name": "郑华", "dept_id": "D007", "center_id": "C003", "role_id": "R001", "email": "zhenghua@jinkang.com", "phone": "13800000010", "is_active": True},
    {"employee_id": "EMP-011", "employee_name": "钱敏", "dept_id": "D008", "center_id": "C003", "role_id": "R007", "email": "qianmin@jinkang.com", "phone": "13800000011", "is_active": True},
    {"employee_id": "EMP-012", "employee_name": "冯磊", "dept_id": "D009", "center_id": "C003", "role_id": "R001", "email": "fenglei@jinkang.com", "phone": "13800000012", "is_active": True},
    {"employee_id": "EMP-013", "employee_name": "陈华南", "dept_id": "D010", "center_id": "C004", "role_id": "R002", "email": "chenhuanan@jinkang.com", "phone": "13800000013", "is_active": True},
    {"employee_id": "EMP-014", "employee_name": "黄涛", "dept_id": "D010", "center_id": "C004", "role_id": "R001", "email": "huangtao@jinkang.com", "phone": "13800000014", "is_active": True},
    {"employee_id": "EMP-015", "employee_name": "林静", "dept_id": "D011", "center_id": "C004", "role_id": "R007", "email": "linjing@jinkang.com", "phone": "13800000015", "is_active": True},
    {"employee_id": "EMP-016", "employee_name": "徐鹏", "dept_id": "D012", "center_id": "C004", "role_id": "R001", "email": "xupeng@jinkang.com", "phone": "13800000016", "is_active": True},
    {"employee_id": "EMP-017", "employee_name": "何财务", "dept_id": "D001", "center_id": "C001", "role_id": "R005", "email": "hecaiwu@jinkang.com", "phone": "13800000017", "is_active": True},
    {"employee_id": "EMP-018", "employee_name": "马法人", "dept_id": "D004", "center_id": "C002", "role_id": "R003", "email": "mafr@jinkang.com", "phone": "13800000018", "is_active": True},
    {"employee_id": "EMP-019", "employee_name": "杨授权", "dept_id": "D007", "center_id": "C003", "role_id": "R004", "email": "yangsq@jinkang.com", "phone": "13800000019", "is_active": True},
    {"employee_id": "EMP-020", "employee_name": "朱员工", "dept_id": "D003", "center_id": "C001", "role_id": "R008", "email": "zhuyg@jinkang.com", "phone": "13800000020", "is_active": True},
]


async def seed_organization(db: AsyncSession) -> None:
    logger.info("Seeding centers...")
    for data in CENTERS:
        existing = await db.get(Department, data["dept_id"])
        if existing is None:
            db.add(Department(**data))
    await db.flush()

    logger.info("Seeding departments...")
    for data in DEPARTMENTS:
        existing = await db.get(Department, data["dept_id"])
        if existing is None:
            db.add(Department(**data))
    await db.flush()

    logger.info("Seeding roles...")
    for data in ROLES:
        existing = await db.get(Role, data["role_id"])
        if existing is None:
            db.add(Role(**data))
    await db.flush()

    logger.info("Seeding employees...")
    for data in EMPLOYEES:
        existing = await db.get(Employee, data["employee_id"])
        if existing is None:
            db.add(Employee(**data))
    await db.flush()

    logger.info("Organization seed completed.")
