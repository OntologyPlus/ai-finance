from datetime import datetime, timedelta
from decimal import Decimal

from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from models.expense import ExpenseReport, BudgetWriteOff
from models.approval import ApprovalRecord
from models.alert import AlertRecord, AlertClosure, AlertEscalation
from models.analysis import ExecutionRate, GapAnalysis, ListAnalysis, MonthlyReport


EXPENSE_REPORTS = [
    {"expense_id": "EXP-001", "applicant_id": "EMP-020", "budget_id": "BG-2026-001", "l1_code": "B1", "l2_code": "B1-1", "l3_code": "B1-1-01", "amount": Decimal("3500.00"), "description": "北京出差机票及住宿", "control_tag": "强管控", "status": "已审批", "center_id": "C001", "department_id": "D003", "legal_entity_id": "LE001"},
    {"expense_id": "EXP-002", "applicant_id": "EMP-007", "budget_id": "BG-2026-005", "l1_code": "B2", "l2_code": None, "l3_code": "B2-00-01", "amount": Decimal("8500.00"), "description": "客户招待费-华北区", "control_tag": "强管控", "status": "已审批", "center_id": "C002", "department_id": "D005", "legal_entity_id": "LE002"},
    {"expense_id": "EXP-003", "applicant_id": "EMP-011", "budget_id": "BG-2026-007", "l1_code": "B6", "l2_code": None, "l3_code": "B6-00-02", "amount": Decimal("45000.00"), "description": "数字营销推广活动", "control_tag": "组合管控", "status": "组织线审批中", "center_id": "C003", "department_id": "D008", "legal_entity_id": "LE003"},
    {"expense_id": "EXP-004", "applicant_id": "EMP-015", "budget_id": "BG-2026-010", "l1_code": "B7", "l2_code": "B7-3", "l3_code": "B7-3-01", "amount": Decimal("120000.00"), "description": "华南区Q2渠道返利", "control_tag": "强管控", "status": "法人线审批中", "center_id": "C004", "department_id": "D011", "legal_entity_id": "LE004"},
    {"expense_id": "EXP-005", "applicant_id": "EMP-002", "budget_id": "BG-2026-002", "l1_code": "B5", "l2_code": "B5-1", "l3_code": "B5-1-01", "amount": Decimal("280000.00"), "description": "研发核心项目人力成本Q2", "control_tag": "强管控", "status": "待审批", "center_id": "C001", "department_id": "D001", "legal_entity_id": "LE001"},
    {"expense_id": "EXP-006", "applicant_id": "EMP-008", "budget_id": "BG-2026-006", "l1_code": "B5", "l2_code": "B5-3", "l3_code": "B5-3-01", "amount": Decimal("95000.00"), "description": "研发外包服务费", "control_tag": "强管控", "status": "已审批", "center_id": "C002", "department_id": "D006", "legal_entity_id": "LE002"},
    {"expense_id": "EXP-007", "applicant_id": "EMP-020", "budget_id": "BG-2026-001", "l1_code": "B1", "l2_code": "B1-1", "l3_code": "B1-1-02", "amount": Decimal("2200.00"), "description": "上海出差酒店", "control_tag": "强管控", "status": "已核销", "center_id": "C001", "department_id": "D003", "legal_entity_id": "LE001"},
    {"expense_id": "EXP-008", "applicant_id": "EMP-014", "budget_id": "BG-2026-011", "l1_code": "B4", "l2_code": None, "l3_code": "B4-00-01", "amount": Decimal("1500.00"), "description": "办公用品采购", "control_tag": "不管控", "status": "已核销", "center_id": "C004", "department_id": "D010", "legal_entity_id": "LE004"},
    {"expense_id": "EXP-009", "applicant_id": "EMP-003", "budget_id": "BG-2026-019", "l1_code": "B6", "l2_code": None, "l3_code": "B6-00-01", "amount": Decimal("50000.00"), "description": "市场推广活动", "control_tag": "强管控", "status": "已驳回", "center_id": "C001", "department_id": "D002", "legal_entity_id": "LE001"},
    {"expense_id": "EXP-010", "applicant_id": "EMP-012", "budget_id": "BG-2026-009", "l1_code": "B5", "l2_code": "B5-2", "l3_code": "B5-2-01", "amount": Decimal("350000.00"), "description": "研发设备采购-服务器", "control_tag": "强管控", "status": "待审批", "center_id": "C003", "department_id": "D009", "legal_entity_id": "LE003"},
    {"expense_id": "EXP-011", "applicant_id": "EMP-006", "budget_id": "BG-2026-013", "l1_code": "B1", "l2_code": "B1-1", "l3_code": "B1-1-01", "amount": Decimal("5200.00"), "description": "华北区差旅-机票", "control_tag": "强管控", "status": "草稿", "center_id": "C002", "department_id": "D004", "legal_entity_id": "LE002"},
    {"expense_id": "EXP-012", "applicant_id": "EMP-016", "budget_id": "BG-2026-015", "l1_code": "B5", "l2_code": "B5-5", "l3_code": "B5-5-01", "amount": Decimal("68000.00"), "description": "技术咨询费", "control_tag": "组合管控", "status": "已审批", "center_id": "C004", "department_id": "D012", "legal_entity_id": "LE004"},
    {"expense_id": "EXP-013", "applicant_id": "EMP-010", "budget_id": "BG-2026-008", "l1_code": "B3", "l2_code": None, "l3_code": "B3-00-01", "amount": Decimal("12000.00"), "description": "内部培训费用", "control_tag": "中心弱管控", "status": "已审批", "center_id": "C003", "department_id": "D007", "legal_entity_id": "LE003"},
    {"expense_id": "EXP-014", "applicant_id": "EMP-004", "budget_id": "BG-2026-003", "l1_code": "B7", "l2_code": "B7-1", "l3_code": "B7-1-01", "amount": Decimal("75000.00"), "description": "渠道拓展活动费", "control_tag": "强管控", "status": "已取消", "center_id": "C001", "department_id": "D003", "legal_entity_id": "LE001"},
    {"expense_id": "EXP-015", "applicant_id": "EMP-017", "budget_id": "BG-2026-016", "l1_code": "B8", "l2_code": None, "l3_code": "B8-00-01", "amount": Decimal("500000.00"), "description": "Q2增值税缴纳", "control_tag": "强管控", "status": "已审批", "center_id": "C001", "department_id": "D001", "legal_entity_id": "LE001"},
]

APPROVAL_RECORDS = [
    {"approval_id": "APR-001", "expense_id": "EXP-001", "approval_line": "组织管理线", "approval_step": 1, "approver_id": "EMP-002", "approver_role": "部门负责人", "approval_action": "通过", "approval_comment": "同意", "approved_at": datetime(2026, 5, 10, 10, 30), "deadline": datetime(2026, 5, 12, 10, 30), "is_overdue": False},
    {"approval_id": "APR-002", "expense_id": "EXP-001", "approval_line": "法人架构线", "approval_step": 2, "approver_id": "EMP-018", "approver_role": "法人财务负责人", "approval_action": "通过", "approval_comment": "同意", "approved_at": datetime(2026, 5, 11, 14, 0), "deadline": datetime(2026, 5, 13, 14, 0), "is_overdue": False},
    {"approval_id": "APR-003", "expense_id": "EXP-002", "approval_line": "组织管理线", "approval_step": 1, "approver_id": "EMP-006", "approver_role": "部门负责人", "approval_action": "通过", "approval_comment": "同意", "approved_at": datetime(2026, 5, 12, 9, 0), "deadline": datetime(2026, 5, 14, 9, 0), "is_overdue": False},
    {"approval_id": "APR-004", "expense_id": "EXP-003", "approval_line": "组织管理线", "approval_step": 1, "approver_id": "EMP-010", "approver_role": "部门负责人", "approval_action": "通过", "approval_comment": "同意", "approved_at": datetime(2026, 5, 15, 11, 0), "deadline": datetime(2026, 5, 17, 11, 0), "is_overdue": False},
    {"approval_id": "APR-005", "expense_id": "EXP-003", "approval_line": "组织管理线", "approval_step": 2, "approver_id": "EMP-009", "approver_role": "中心总经理", "approval_action": "待审批", "approval_comment": None, "approved_at": None, "deadline": datetime(2026, 5, 20, 11, 0), "is_overdue": False},
    {"approval_id": "APR-006", "expense_id": "EXP-004", "approval_line": "组织管理线", "approval_step": 1, "approver_id": "EMP-014", "approver_role": "部门负责人", "approval_action": "通过", "approval_comment": "同意", "approved_at": datetime(2026, 5, 14, 16, 0), "deadline": datetime(2026, 5, 16, 16, 0), "is_overdue": False},
    {"approval_id": "APR-007", "expense_id": "EXP-004", "approval_line": "组织管理线", "approval_step": 2, "approver_id": "EMP-013", "approver_role": "中心总经理", "approval_action": "通过", "approval_comment": "同意", "approved_at": datetime(2026, 5, 16, 10, 0), "deadline": datetime(2026, 5, 18, 10, 0), "is_overdue": False},
    {"approval_id": "APR-008", "expense_id": "EXP-004", "approval_line": "法人架构线", "approval_step": 3, "approver_id": "EMP-019", "approver_role": "法人或授权人", "approval_action": "待审批", "approval_comment": None, "approved_at": None, "deadline": datetime(2026, 5, 22, 10, 0), "is_overdue": False},
    {"approval_id": "APR-009", "expense_id": "EXP-005", "approval_line": "组织管理线", "approval_step": 1, "approver_id": "EMP-002", "approver_role": "部门负责人", "approval_action": "待审批", "approval_comment": None, "approved_at": None, "deadline": datetime(2026, 5, 25, 10, 0), "is_overdue": False},
    {"approval_id": "APR-010", "expense_id": "EXP-006", "approval_line": "组织管理线", "approval_step": 1, "approver_id": "EMP-008", "approver_role": "部门负责人", "approval_action": "通过", "approval_comment": "同意", "approved_at": datetime(2026, 5, 8, 14, 0), "deadline": datetime(2026, 5, 10, 14, 0), "is_overdue": False},
    {"approval_id": "APR-011", "expense_id": "EXP-006", "approval_line": "法人架构线", "approval_step": 2, "approver_id": "EMP-018", "approver_role": "法人财务负责人", "approval_action": "通过", "approval_comment": "同意", "approved_at": datetime(2026, 5, 9, 16, 0), "deadline": datetime(2026, 5, 11, 16, 0), "is_overdue": False},
    {"approval_id": "APR-012", "expense_id": "EXP-009", "approval_line": "组织管理线", "approval_step": 1, "approver_id": "EMP-003", "approver_role": "部门负责人", "approval_action": "驳回", "approval_comment": "预算项目尚未审批通过，不可报销", "approved_at": datetime(2026, 5, 13, 10, 0), "deadline": datetime(2026, 5, 15, 10, 0), "is_overdue": False},
    {"approval_id": "APR-013", "expense_id": "EXP-010", "approval_line": "组织管理线", "approval_step": 1, "approver_id": "EMP-012", "approver_role": "部门负责人", "approval_action": "待审批", "approval_comment": None, "approved_at": None, "deadline": datetime(2026, 5, 28, 10, 0), "is_overdue": False},
    {"approval_id": "APR-014", "expense_id": "EXP-012", "approval_line": "组织管理线", "approval_step": 1, "approver_id": "EMP-016", "approver_role": "部门负责人", "approval_action": "通过", "approval_comment": "同意", "approved_at": datetime(2026, 5, 18, 9, 30), "deadline": datetime(2026, 5, 20, 9, 30), "is_overdue": False},
    {"approval_id": "APR-015", "expense_id": "EXP-012", "approval_line": "法人架构线", "approval_step": 2, "approver_id": "EMP-019", "approver_role": "法人或授权人", "approval_action": "通过", "approval_comment": "同意", "approved_at": datetime(2026, 5, 19, 15, 0), "deadline": datetime(2026, 5, 21, 15, 0), "is_overdue": False},
    {"approval_id": "APR-016", "expense_id": "EXP-013", "approval_line": "组织管理线", "approval_step": 1, "approver_id": "EMP-010", "approver_role": "部门负责人", "approval_action": "通过", "approval_comment": "同意", "approved_at": datetime(2026, 5, 16, 11, 0), "deadline": datetime(2026, 5, 18, 11, 0), "is_overdue": False},
    {"approval_id": "APR-017", "expense_id": "EXP-015", "approval_line": "组织管理线", "approval_step": 1, "approver_id": "EMP-002", "approver_role": "部门负责人", "approval_action": "通过", "approval_comment": "同意", "approved_at": datetime(2026, 5, 20, 9, 0), "deadline": datetime(2026, 5, 22, 9, 0), "is_overdue": False},
    {"approval_id": "APR-018", "expense_id": "EXP-015", "approval_line": "法人架构线", "approval_step": 2, "approver_id": "EMP-018", "approver_role": "法人财务负责人", "approval_action": "通过", "approval_comment": "同意", "approved_at": datetime(2026, 5, 21, 14, 0), "deadline": datetime(2026, 5, 23, 14, 0), "is_overdue": False},
    {"approval_id": "APR-019", "expense_id": "EXP-007", "approval_line": "组织管理线", "approval_step": 1, "approver_id": "EMP-004", "approver_role": "部门负责人", "approval_action": "通过", "approval_comment": "同意", "approved_at": datetime(2026, 5, 5, 10, 0), "deadline": datetime(2026, 5, 7, 10, 0), "is_overdue": False},
    {"approval_id": "APR-020", "expense_id": "EXP-008", "approval_line": "组织管理线", "approval_step": 1, "approver_id": "EMP-014", "approver_role": "部门负责人", "approval_action": "通过", "approval_comment": "同意", "approved_at": datetime(2026, 5, 6, 14, 0), "deadline": datetime(2026, 5, 8, 14, 0), "is_overdue": False},
    {"approval_id": "APR-021", "expense_id": "EXP-014", "approval_line": "组织管理线", "approval_step": 1, "approver_id": "EMP-004", "approver_role": "部门负责人", "approval_action": "驳回", "approval_comment": "项目已取消", "approved_at": datetime(2026, 5, 11, 9, 0), "deadline": datetime(2026, 5, 13, 9, 0), "is_overdue": False},
    {"approval_id": "APR-022", "expense_id": "EXP-002", "approval_line": "法人架构线", "approval_step": 2, "approver_id": "EMP-018", "approver_role": "法人财务负责人", "approval_action": "通过", "approval_comment": "同意", "approved_at": datetime(2026, 5, 13, 10, 0), "deadline": datetime(2026, 5, 15, 10, 0), "is_overdue": False},
    {"approval_id": "APR-023", "expense_id": "EXP-013", "approval_line": "法人架构线", "approval_step": 2, "approver_id": "EMP-019", "approver_role": "法人或授权人", "approval_action": "通过", "approval_comment": "同意", "approved_at": datetime(2026, 5, 17, 10, 0), "deadline": datetime(2026, 5, 19, 10, 0), "is_overdue": False},
    {"approval_id": "APR-024", "expense_id": "EXP-007", "approval_line": "法人架构线", "approval_step": 2, "approver_id": "EMP-018", "approver_role": "法人财务负责人", "approval_action": "通过", "approval_comment": "同意", "approved_at": datetime(2026, 5, 6, 16, 0), "deadline": datetime(2026, 5, 8, 16, 0), "is_overdue": False},
    {"approval_id": "APR-025", "expense_id": "EXP-008", "approval_line": "法人架构线", "approval_step": 2, "approver_id": "EMP-019", "approver_role": "法人或授权人", "approval_action": "通过", "approval_comment": "同意", "approved_at": datetime(2026, 5, 7, 11, 0), "deadline": datetime(2026, 5, 9, 11, 0), "is_overdue": False},
]

ALERT_RECORDS = [
    {"alert_id": "ALT-001", "alert_level": "蓝色", "alert_type": "月度执行进度", "alert_status": "已闭环", "l1_code": "B1", "l2_code": "B1-1", "l3_code": "B1-1-01", "budget_id": "BG-2026-013", "project_id": None, "trigger_value": Decimal("650000.00"), "threshold_value": Decimal("640000.00"), "deviation_rate": Decimal("1.56"), "responsible_person": "EMP-006", "response_deadline": datetime(2026, 5, 20, 18, 0), "response_hours": 48, "notification_targets": '["EMP-006","EMP-005"]'},
    {"alert_id": "ALT-002", "alert_level": "黄色", "alert_type": "月度执行进度", "alert_status": "响应中", "l1_code": "B5", "l2_code": "B5-1", "l3_code": "B5-1-01", "budget_id": "BG-2026-002", "project_id": "PRJ-001", "trigger_value": Decimal("1500000.00"), "threshold_value": Decimal("1400000.00"), "deviation_rate": Decimal("7.14"), "responsible_person": "EMP-004", "response_deadline": datetime(2026, 5, 22, 18, 0), "response_hours": 36, "notification_targets": '["EMP-004","EMP-001"]'},
    {"alert_id": "ALT-003", "alert_level": "红色", "alert_type": "月度执行进度", "alert_status": "开放", "l1_code": "B1", "l2_code": "B1-1", "l3_code": "B1-1-01", "budget_id": "BG-2026-013", "project_id": None, "trigger_value": Decimal("650000.00"), "threshold_value": Decimal("600000.00"), "deviation_rate": Decimal("8.33"), "responsible_person": "EMP-006", "response_deadline": datetime(2026, 5, 21, 12, 0), "response_hours": 24, "notification_targets": '["EMP-006","EMP-005","EMP-018"]'},
    {"alert_id": "ALT-004", "alert_level": "蓝色", "alert_type": "季度滚动预测", "alert_status": "已闭环", "l1_code": "B6", "l2_code": None, "l3_code": "B6-00-01", "budget_id": "BG-2026-004", "project_id": None, "trigger_value": Decimal("2100000.00"), "threshold_value": Decimal("2000000.00"), "deviation_rate": Decimal("5.00"), "responsible_person": "EMP-007", "response_deadline": datetime(2026, 5, 25, 18, 0), "response_hours": 72, "notification_targets": '["EMP-007","EMP-005"]'},
    {"alert_id": "ALT-005", "alert_level": "黄色", "alert_type": "季度滚动预测", "alert_status": "待闭环确认", "l1_code": "B7", "l2_code": "B7-1", "l3_code": "B7-1-01", "budget_id": "BG-2026-003", "project_id": "PRJ-002", "trigger_value": Decimal("880000.00"), "threshold_value": Decimal("800000.00"), "deviation_rate": Decimal("10.00"), "responsible_person": "EMP-003", "response_deadline": datetime(2026, 5, 23, 18, 0), "response_hours": 48, "notification_targets": '["EMP-003","EMP-001"]'},
    {"alert_id": "ALT-006", "alert_level": "红色", "alert_type": "季度滚动预测", "alert_status": "开放", "l1_code": "B5", "l2_code": "B5-3", "l3_code": "B5-3-01", "budget_id": "BG-2026-006", "project_id": "PRJ-003", "trigger_value": Decimal("720000.00"), "threshold_value": Decimal("600000.00"), "deviation_rate": Decimal("20.00"), "responsible_person": "EMP-008", "response_deadline": datetime(2026, 5, 21, 18, 0), "response_hours": 24, "notification_targets": '["EMP-008","EMP-005","EMP-018"]'},
    {"alert_id": "ALT-007", "alert_level": "橙色", "alert_type": "里程碑", "alert_status": "响应中", "l1_code": "B5", "l2_code": "B5-1", "l3_code": "B5-1-01", "budget_id": "BG-2026-002", "project_id": "PRJ-001", "trigger_value": Decimal("1500000.00"), "threshold_value": Decimal("1400000.00"), "deviation_rate": Decimal("7.14"), "responsible_person": "EMP-004", "response_deadline": datetime(2026, 5, 24, 18, 0), "response_hours": 48, "notification_targets": '["EMP-004","EMP-001","EMP-017"]'},
    {"alert_id": "ALT-008", "alert_level": "蓝色", "alert_type": "L1专项", "alert_status": "已闭环", "l1_code": "B9", "l2_code": None, "l3_code": "B9-00-01", "budget_id": "BG-2026-012", "project_id": None, "trigger_value": Decimal("2200000.00"), "threshold_value": Decimal("2100000.00"), "deviation_rate": Decimal("4.76"), "responsible_person": "EMP-002", "response_deadline": datetime(2026, 5, 18, 18, 0), "response_hours": 72, "notification_targets": '["EMP-002","EMP-001"]'},
    {"alert_id": "ALT-009", "alert_level": "黄色", "alert_type": "L1专项", "alert_status": "开放", "l1_code": "B2", "l2_code": None, "l3_code": "B2-00-01", "budget_id": "BG-2026-005", "project_id": None, "trigger_value": Decimal("320000.00"), "threshold_value": Decimal("275000.00"), "deviation_rate": Decimal("16.36"), "responsible_person": "EMP-007", "response_deadline": datetime(2026, 5, 22, 18, 0), "response_hours": 36, "notification_targets": '["EMP-007","EMP-005"]'},
    {"alert_id": "ALT-010", "alert_level": "红色", "alert_type": "L1专项", "alert_status": "已升级", "l1_code": "B7", "l2_code": "B7-3", "l3_code": "B7-3-01", "budget_id": "BG-2026-010", "project_id": None, "trigger_value": Decimal("700000.00"), "threshold_value": Decimal("525000.00"), "deviation_rate": Decimal("33.33"), "responsible_person": "EMP-015", "response_deadline": datetime(2026, 5, 18, 12, 0), "response_hours": 24, "notification_targets": '["EMP-015","EMP-013","EMP-019"]'},
]

ALERT_CLOSURES = [
    {"closure_id": "CLS-001", "alert_id": "ALT-001", "business_response": "华北差旅费超支因Q2项目出差增加，已调整后续出差计划", "business_responder": "EMP-006", "business_response_at": datetime(2026, 5, 19, 10, 0), "bp_confirmation": "确认原因合理，建议控制Q3差旅预算", "bp_confirmer": "EMP-017", "bp_confirmation_at": datetime(2026, 5, 19, 15, 0), "closure_status": "已闭环", "retention_period": 3},
    {"closure_id": "CLS-002", "alert_id": "ALT-004", "business_response": "品牌推广超预算因新增线上渠道投放，预计Q3可回收", "business_responder": "EMP-007", "business_response_at": datetime(2026, 5, 23, 11, 0), "bp_confirmation": "确认，建议Q3关注ROI", "bp_confirmer": "EMP-017", "bp_confirmation_at": datetime(2026, 5, 23, 16, 0), "closure_status": "已闭环", "retention_period": 3},
    {"closure_id": "CLS-003", "alert_id": "ALT-008", "business_response": "人力成本超支因年中调薪，已在预算调整中处理", "business_responder": "EMP-002", "business_response_at": datetime(2026, 5, 17, 9, 0), "bp_confirmation": "确认，已纳入预算调整流程", "bp_confirmer": "EMP-017", "bp_confirmation_at": datetime(2026, 5, 17, 14, 0), "closure_status": "已闭环", "retention_period": 3},
]

ALERT_ESCALATIONS = [
    {"escalation_id": "ESC-001", "alert_id": "ALT-010", "escalation_reason": "超时未响应", "escalation_level": "中心总经理", "escalation_target": "EMP-013", "original_deadline": datetime(2026, 5, 18, 12, 0), "escalation_at": datetime(2026, 5, 18, 14, 0), "is_performance_impact": True},
    {"escalation_id": "ESC-002", "alert_id": "ALT-003", "escalation_reason": "超时未闭环", "escalation_level": "中心总经理", "escalation_target": "EMP-005", "original_deadline": datetime(2026, 5, 21, 12, 0), "escalation_at": datetime(2026, 5, 21, 14, 0), "is_performance_impact": False},
]

EXECUTION_RATES = [
    {"id": "ER-001", "period": "2026-05", "l1_code": "B1", "l2_code": "B1-1", "l3_code": "B1-1-01", "center_id": "C001", "monthly_plan": Decimal("100000.00"), "monthly_actual": Decimal("98000.00"), "cumulative_plan": Decimal("500000.00"), "cumulative_actual": Decimal("480000.00"), "annual_budget": Decimal("1200000.00"), "monthly_rate": Decimal("98.00"), "cumulative_rate": Decimal("96.00"), "annual_rate": Decimal("40.00")},
    {"id": "ER-002", "period": "2026-05", "l1_code": "B5", "l2_code": "B5-1", "l3_code": "B5-1-01", "center_id": "C001", "monthly_plan": Decimal("300000.00"), "monthly_actual": Decimal("350000.00"), "cumulative_plan": Decimal("1400000.00"), "cumulative_actual": Decimal("1500000.00"), "annual_budget": Decimal("3500000.00"), "monthly_rate": Decimal("116.67"), "cumulative_rate": Decimal("107.14"), "annual_rate": Decimal("42.86")},
    {"id": "ER-003", "period": "2026-05", "l1_code": "B7", "l2_code": "B7-1", "l3_code": "B7-1-01", "center_id": "C001", "monthly_plan": Decimal("60000.00"), "monthly_actual": Decimal("55000.00"), "cumulative_plan": Decimal("300000.00"), "cumulative_actual": Decimal("280000.00"), "annual_budget": Decimal("800000.00"), "monthly_rate": Decimal("91.67"), "cumulative_rate": Decimal("93.33"), "annual_rate": Decimal("35.00")},
    {"id": "ER-004", "period": "2026-05", "l1_code": "B6", "l2_code": None, "l3_code": "B6-00-01", "center_id": "C002", "monthly_plan": Decimal("180000.00"), "monthly_actual": Decimal("200000.00"), "cumulative_plan": Decimal("900000.00"), "cumulative_actual": Decimal("950000.00"), "annual_budget": Decimal("2000000.00"), "monthly_rate": Decimal("111.11"), "cumulative_rate": Decimal("105.56"), "annual_rate": Decimal("47.50")},
    {"id": "ER-005", "period": "2026-05", "l1_code": "B9", "l2_code": None, "l3_code": "B9-00-01", "center_id": "C001", "monthly_plan": Decimal("420000.00"), "monthly_actual": Decimal("430000.00"), "cumulative_plan": Decimal("2100000.00"), "cumulative_actual": Decimal("2200000.00"), "annual_budget": Decimal("5000000.00"), "monthly_rate": Decimal("102.38"), "cumulative_rate": Decimal("104.76"), "annual_rate": Decimal("44.00")},
]

GAP_ANALYSES = [
    {"id": "GA-001", "period": "2026-Q2", "center_id": "C001", "l1_code": "B5", "gap1": Decimal("500000.00"), "gap2": Decimal("150000.00"), "gap3": Decimal("80000.00"), "gap1_detail": '{"target": "3500000", "actual_plan": "3000000", "gap": "500000", "reason": "研发项目增加导致预算不足"}', "gap2_detail": '{"plan": "1400000", "actual": "1550000", "gap": "150000", "reason": "人力成本超支"}', "gap3_detail": '{"current_forecast": "3580000", "original_plan": "3500000", "gap": "80000", "reason": "外包费用上涨"}'},
]

LIST_ANALYSES = [
    {"id": "LA-001", "period": "2026-Q2", "center_id": "C001", "list_type": "List1", "item_name": "研发核心项目预算追加", "l1_code": "B5", "amount": Decimal("500000.00"), "description": "GAP1目标差距需追加研发预算", "action_plan": "向管委会申请追加研发预算500万"},
]

MONTHLY_REPORTS = [
    {"id": "MR-001", "period": "2026-04", "report_type": "月度快报", "center_id": "C001", "content": '{"execution_summary": "4月预算执行率96%，整体正常", "alert_summary": "蓝色预警2个，黄色预警1个", "key_risks": "研发费执行率偏高"}', "file_path": "/reports/2026-04/C001_monthly.pdf", "status": "已定稿", "finalized_at": datetime(2026, 5, 5, 18, 0)},
    {"id": "MR-002", "period": "2026-05", "report_type": "月度快报", "center_id": "C001", "content": '{"execution_summary": "5月预算执行率98%，需关注研发费和差旅费", "alert_summary": "黄色预警2个，红色预警1个", "key_risks": "差旅费超预算，研发费执行率107%"}', "file_path": None, "status": "编制中", "finalized_at": None},
]


async def seed_demo_data(db: AsyncSession) -> None:
    logger.info("Seeding expense reports...")
    for data in EXPENSE_REPORTS:
        existing = await db.get(ExpenseReport, data["expense_id"])
        if existing is None:
            db.add(ExpenseReport(**data))
    await db.flush()

    logger.info("Seeding approval records...")
    for data in APPROVAL_RECORDS:
        existing = await db.get(ApprovalRecord, data["approval_id"])
        if existing is None:
            db.add(ApprovalRecord(**data))
    await db.flush()

    logger.info("Seeding alert records...")
    for data in ALERT_RECORDS:
        existing = await db.get(AlertRecord, data["alert_id"])
        if existing is None:
            db.add(AlertRecord(**data))
    await db.flush()

    logger.info("Seeding alert closures...")
    for data in ALERT_CLOSURES:
        existing = await db.get(AlertClosure, data["closure_id"])
        if existing is None:
            db.add(AlertClosure(**data))
    await db.flush()

    logger.info("Seeding alert escalations...")
    for data in ALERT_ESCALATIONS:
        existing = await db.get(AlertEscalation, data["escalation_id"])
        if existing is None:
            db.add(AlertEscalation(**data))
    await db.flush()

    logger.info("Seeding execution rates...")
    for data in EXECUTION_RATES:
        existing = await db.get(ExecutionRate, data["id"])
        if existing is None:
            db.add(ExecutionRate(**data))
    await db.flush()

    logger.info("Seeding GAP analyses...")
    for data in GAP_ANALYSES:
        existing = await db.get(GapAnalysis, data["id"])
        if existing is None:
            db.add(GapAnalysis(**data))
    await db.flush()

    logger.info("Seeding List analyses...")
    for data in LIST_ANALYSES:
        existing = await db.get(ListAnalysis, data["id"])
        if existing is None:
            db.add(ListAnalysis(**data))
    await db.flush()

    logger.info("Seeding monthly reports...")
    for data in MONTHLY_REPORTS:
        existing = await db.get(MonthlyReport, data["id"])
        if existing is None:
            db.add(MonthlyReport(**data))
    await db.flush()

    logger.info("Demo data seed completed.")
