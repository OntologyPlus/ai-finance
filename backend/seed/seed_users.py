from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from models.user import User, UserRole
from api.auth import get_password_hash


USERS = [
    {
        "user_id": "U001",
        "username": "admin",
        "password_hash": get_password_hash("admin123"),
        "display_name": "系统管理员",
        "role": UserRole.ADMIN.value,
        "center_id": None,
        "department_id": None,
        "is_active": True,
    },
    {
        "user_id": "U002",
        "username": "cfo_zhang",
        "password_hash": get_password_hash("admin123"),
        "display_name": "张津康",
        "role": UserRole.CFO.value,
        "center_id": "C001",
        "department_id": "D001",
        "is_active": True,
    },
    {
        "user_id": "U003",
        "username": "center_mgr_li",
        "password_hash": get_password_hash("admin123"),
        "display_name": "刘华北",
        "role": UserRole.CENTER_MANAGER.value,
        "center_id": "C002",
        "department_id": "D004",
        "is_active": True,
    },
    {
        "user_id": "U004",
        "username": "dept_head_wang",
        "password_hash": get_password_hash("admin123"),
        "display_name": "王芳",
        "role": UserRole.DEPT_HEAD.value,
        "center_id": "C001",
        "department_id": "D002",
        "is_active": True,
    },
    {
        "user_id": "U005",
        "username": "finance_bp_chen",
        "password_hash": get_password_hash("admin123"),
        "display_name": "何财务",
        "role": UserRole.FINANCE_BP.value,
        "center_id": "C001",
        "department_id": "D001",
        "is_active": True,
    },
    {
        "user_id": "U006",
        "username": "employee_zhao",
        "password_hash": get_password_hash("admin123"),
        "display_name": "朱员工",
        "role": UserRole.EMPLOYEE.value,
        "center_id": "C001",
        "department_id": "D003",
        "is_active": True,
    },
    {
        "user_id": "U007",
        "username": "center_mgr_wu",
        "password_hash": get_password_hash("admin123"),
        "display_name": "吴华东",
        "role": UserRole.CENTER_MANAGER.value,
        "center_id": "C003",
        "department_id": "D007",
        "is_active": True,
    },
    {
        "user_id": "U008",
        "username": "dept_head_chen",
        "password_hash": get_password_hash("admin123"),
        "display_name": "陈刚",
        "role": UserRole.DEPT_HEAD.value,
        "center_id": "C002",
        "department_id": "D004",
        "is_active": True,
    },
]


async def seed_users(db: AsyncSession) -> None:
    logger.info("Seeding users...")
    for data in USERS:
        existing = await db.get(User, data["user_id"])
        if existing is None:
            db.add(User(**data))
    await db.flush()
    logger.info(f"User seed completed. {len(USERS)} users ready.")
