from pydantic import BaseModel, Field
from typing import Optional, List, Any
from datetime import datetime, date
from enum import Enum


class ManagementMode(str, Enum):
    PROJECT = "项目化管理"
    GENERAL = "通用管控"
    COMPLIANCE = "合规导向"


class AlertRuleType(str, Enum):
    GENERAL = "通用规则"
    GENERAL_SPECIAL = "通用+专项"


class BudgetCategory(str, Enum):
    A = "A"
    B = "B"


class Quadrant(str, Enum):
    DEVELOP = "发展"
    SHRINK = "收缩"
    STABLE = "稳定"
    EXPLORE = "探索"


class BudgetStatus(str, Enum):
    DRAFT = "编制中"
    PENDING_APPROVAL = "待审批"
    GRANTED = "已授予"
    EXECUTING = "执行中"
    FROZEN = "已冻结"
    WRITTEN_OFF = "已核销"
    CANCELLED = "已取消"


class ControlModeEnum(str, Enum):
    STRONG = "强管控"
    WEAK_CENTER = "中心弱管控"
    COMBINED = "组合管控"
    NONE = "不管控"


class B2AApprovalStatus(str, Enum):
    PENDING = "待审批"
    APPROVED = "已通过"
    REJECTED = "已驳回"


class MilestonePeriod(str, Enum):
    Q1 = "Q1"
    Q2 = "Q2"
    Q3 = "Q3"
    Q4 = "Q4"


class ApprovalLine(str, Enum):
    ORG = "组织管理线"
    LEGAL = "法人架构线"


class ApproverRole(str, Enum):
    DEPT_HEAD = "部门负责人"
    CENTER_GM = "中心总经理"
    LEGAL_FINANCE = "法人财务负责人"
    LEGAL_AUTH = "法人或授权人"


class ApprovalAction(str, Enum):
    APPROVED = "通过"
    REJECTED = "驳回"
    PENDING = "待审批"


class AlertLevel(str, Enum):
    BLUE = "蓝色"
    YELLOW = "黄色"
    ORANGE = "橙色"
    RED = "红色"


class AlertType(str, Enum):
    MONTHLY = "月度执行进度"
    QUARTERLY = "季度滚动预测"
    MILESTONE = "里程碑"
    L1_SPECIAL = "L1专项"


class AlertStatus(str, Enum):
    OPEN = "开放"
    RESPONDING = "响应中"
    PENDING_CLOSURE = "待闭环确认"
    CLOSED = "已闭环"
    ESCALATED = "已升级"


class ClosureStatus(str, Enum):
    PENDING_RESPONSE = "待业务响应"
    PENDING_BP = "待BP确认"
    CLOSED = "已闭环"
    REJECTED = "已驳回"


class EscalationReason(str, Enum):
    TIMEOUT_NO_RESPONSE = "超时未响应"
    TIMEOUT_NO_CLOSURE = "超时未闭环"


class ExpenseStatus(str, Enum):
    DRAFT = "草稿"
    PENDING_APPROVAL = "待审批"
    ORG_APPROVING = "组织线审批中"
    LEGAL_APPROVING = "法人线审批中"
    APPROVED = "已审批"
    REJECTED = "已驳回"
    WRITTEN_OFF = "已核销"
    CANCELLED = "已取消"


class StrategicIntentL1(str, Enum):
    COMMERCIALIZATION = "全渠道商业化"
    INNOVATION = "创新研发"
    INTERNATIONAL = "国际化"


class BudgetSubjectL1Base(BaseModel):
    l1_code: str = Field(..., max_length=2, description="L1科目编码")
    l1_name: str = Field(..., max_length=50, description="L1科目名称")
    management_mode: ManagementMode = Field(..., description="管控模式")
    alert_rule_type: AlertRuleType = Field(..., description="预警规则类型")
    has_l2: bool = Field(..., description="是否含L2子类")
    description: Optional[str] = Field(None, description="自然语言定义")


class BudgetSubjectL1Create(BudgetSubjectL1Base):
    pass


class BudgetSubjectL1Read(BudgetSubjectL1Base):
    model_config = {"from_attributes": True}


class BudgetSubjectL2Base(BaseModel):
    l2_code: str = Field(..., max_length=5, description="L2科目编码")
    l2_name: str = Field(..., max_length=100, description="L2科目名称")
    l1_code: str = Field(..., max_length=2, description="归属L1编码")
    special_rules: Optional[str] = Field(None, description="特殊规则")
    roi_threshold: Optional[str] = Field(None, description="ROI预警阈值")


class BudgetSubjectL2Create(BudgetSubjectL2Base):
    pass


class BudgetSubjectL2Read(BudgetSubjectL2Base):
    model_config = {"from_attributes": True}


class BudgetSubjectL3Base(BaseModel):
    l3_code: str = Field(..., max_length=10, description="L3科目编码")
    l3_name: str = Field(..., max_length=100, description="L3科目名称")
    l2_code: Optional[str] = Field(None, max_length=5, description="归属L2编码")
    l1_code: str = Field(..., max_length=2, description="归属L1编码")
    control_tag: ControlModeEnum = Field(..., description="管控级别标签")
    variety_group: Optional[str] = Field(None, max_length=20, description="品种组编码")
    is_project_managed: bool = Field(False, description="是否项目化管理")
    alert_rules: Optional[List[str]] = Field(None, description="适用的预警规则ID列表")


class BudgetSubjectL3Create(BudgetSubjectL3Base):
    pass


class BudgetSubjectL3Read(BudgetSubjectL3Base):
    model_config = {"from_attributes": True}


class BudgetItemBase(BaseModel):
    budget_id: str = Field(..., max_length=20, description="预算项目唯一标识")
    budget_name: str = Field(..., max_length=200, description="预算项目名称")
    budget_category: BudgetCategory = Field(..., description="A/B类别")
    l1_code: str = Field(..., max_length=2, description="归属L1科目")
    l2_code: Optional[str] = Field(None, max_length=5, description="归属L2科目")
    l3_code: Optional[str] = Field(None, max_length=10, description="归属L3科目")
    quadrant: Quadrant = Field(..., description="象限归属")
    strategy_initiative_id: Optional[str] = Field(None, max_length=20, description="对标战略举措编号")
    annual_amount: float = Field(..., description="年度预算总额")
    granted_amount: float = Field(0, description="已授予额度")
    frozen_amount: float = Field(0, description="已冻结额度")
    used_amount: float = Field(0, description="已使用额度")
    available_amount: float = Field(0, description="可用额度")
    grant_percentage: float = Field(0, description="授予比例")
    status: BudgetStatus = Field(BudgetStatus.DRAFT, description="预算项目状态")
    center_id: Optional[str] = Field(None, max_length=10, description="归属中心")
    department_id: Optional[str] = Field(None, max_length=10, description="归属部门")
    project_id: Optional[str] = Field(None, max_length=20, description="关联项目ID")
    pending_project_budget_id: Optional[str] = Field(None, max_length=20, description="暂存项目预算ID")
    strategic_intent_l1: Optional[StrategicIntentL1] = Field(None, description="战略意图L1(三大战略方向)")
    strategic_intent_l2: Optional[str] = Field(None, max_length=100, description="战略意图L2(产品线×区域)")
    product_line: Optional[str] = Field(None, max_length=50, description="产品线")
    region: Optional[str] = Field(None, max_length=50, description="区域")
    product_variety: Optional[str] = None
    channel: Optional[str] = None


class BudgetItemCreate(BudgetItemBase):
    pass


class BudgetItemRead(BudgetItemBase):
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    model_config = {"from_attributes": True}


class B2AConversionBase(BaseModel):
    conversion_id: str = Field(..., max_length=20, description="转换记录编号")
    budget_id: str = Field(..., max_length=20, description="预算项目ID")
    conversion_date: date = Field(..., description="转换日期")
    milestone_evidence: Optional[str] = Field(None, description="里程碑达标证据")
    milestone_period: MilestonePeriod = Field(..., description="里程碑验证季度")
    approver: Optional[str] = Field(None, max_length=50, description="审批人")
    approval_status: B2AApprovalStatus = Field(B2AApprovalStatus.PENDING, description="审批状态")
    pre_category: BudgetCategory = Field(BudgetCategory.B, description="转换前类别")
    post_category: BudgetCategory = Field(BudgetCategory.A, description="转换后类别")
    frozen_amount: Optional[float] = Field(None, description="转换后冻结额度")
    report_to_committee: bool = Field(False, description="是否已向管委会提交专项报告")


class B2AConversionCreate(B2AConversionBase):
    pass


class B2AConversionRead(B2AConversionBase):
    created_at: Optional[datetime] = None
    model_config = {"from_attributes": True}


class ControlModeBase(BaseModel):
    mode: str = Field(..., max_length=20, description="管控模式名称")
    code: str = Field(..., max_length=20, description="管控模式编码")
    cross_dept_allowed: bool = Field(..., description="可否跨部门")
    cross_category_allowed: bool = Field(..., description="可否跨费用类别")
    cross_variety_group_allowed: bool = Field(..., description="可否跨品种组")
    over_budget_action: str = Field(..., description="超预算处理")
    description: Optional[str] = Field(None, description="描述")


class ControlModeRead(ControlModeBase):
    model_config = {"from_attributes": True}


class ApprovalRecordBase(BaseModel):
    approval_id: str = Field(..., max_length=20, description="审批记录编号")
    expense_id: str = Field(..., max_length=20, description="报销单号")
    approval_line: ApprovalLine = Field(..., description="审批线路")
    approval_step: int = Field(..., description="审批步骤序号")
    approver_id: str = Field(..., max_length=20, description="审批人ID")
    approver_role: ApproverRole = Field(..., description="审批人角色")
    approval_action: ApprovalAction = Field(ApprovalAction.PENDING, description="审批动作")
    approval_comment: Optional[str] = Field(None, description="审批意见")
    deadline: Optional[datetime] = Field(None, description="审批截止时间")
    is_overdue: bool = Field(False, description="是否超时")


class ApprovalRecordCreate(ApprovalRecordBase):
    pass


class ApprovalRecordRead(ApprovalRecordBase):
    approved_at: Optional[datetime] = None
    model_config = {"from_attributes": True}


class AlertRecordBase(BaseModel):
    alert_id: str = Field(..., max_length=20, description="预警编号")
    alert_level: AlertLevel = Field(..., description="预警级别")
    alert_type: AlertType = Field(..., description="预警类型")
    alert_status: AlertStatus = Field(AlertStatus.OPEN, description="预警状态")
    l1_code: Optional[str] = Field(None, max_length=2, description="关联L1科目")
    l2_code: Optional[str] = Field(None, max_length=5, description="关联L2科目")
    l3_code: Optional[str] = Field(None, max_length=10, description="关联L3科目")
    budget_id: Optional[str] = Field(None, max_length=20, description="关联预算ID")
    project_id: Optional[str] = Field(None, max_length=20, description="关联项目ID")
    trigger_value: Optional[float] = Field(None, description="触发值")
    threshold_value: Optional[float] = Field(None, description="阈值")
    deviation_rate: Optional[float] = Field(None, description="偏离率(%)")
    responsible_person: Optional[str] = Field(None, max_length=50, description="责任人")
    response_deadline: Optional[datetime] = Field(None, description="响应截止时间")
    response_hours: Optional[int] = Field(None, description="响应时限（小时）")
    notification_targets: Optional[List[str]] = Field(None, description="通知对象列表")


class AlertRecordCreate(AlertRecordBase):
    pass


class AlertRecordRead(AlertRecordBase):
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    model_config = {"from_attributes": True}


class AlertClosureBase(BaseModel):
    closure_id: str = Field(..., max_length=20, description="闭环档案编号")
    alert_id: str = Field(..., max_length=20, description="预警编号")
    business_response: Optional[str] = Field(None, description="业务单元整改方案")
    business_responder: Optional[str] = Field(None, max_length=50, description="业务响应人")
    business_response_at: Optional[datetime] = Field(None, description="业务响应时间")
    bp_confirmation: Optional[str] = Field(None, description="财经BP确认意见")
    bp_confirmer: Optional[str] = Field(None, max_length=50, description="财经BP确认人")
    bp_confirmation_at: Optional[datetime] = Field(None, description="BP确认时间")
    closure_status: ClosureStatus = Field(ClosureStatus.PENDING_RESPONSE, description="闭环状态")
    retention_period: int = Field(3, description="存档年限（≥3年）")


class AlertClosureCreate(AlertClosureBase):
    pass


class AlertClosureRead(AlertClosureBase):
    created_at: Optional[datetime] = None
    model_config = {"from_attributes": True}


class AlertEscalationBase(BaseModel):
    escalation_id: str = Field(..., max_length=20, description="升级记录编号")
    alert_id: str = Field(..., max_length=20, description="预警编号")
    escalation_reason: EscalationReason = Field(..., description="升级原因")
    escalation_level: Optional[str] = Field(None, max_length=50, description="升级通知对象级别")
    escalation_target: Optional[str] = Field(None, max_length=50, description="升级通知目标人")
    original_deadline: Optional[datetime] = Field(None, description="原响应截止时间")
    escalation_at: Optional[datetime] = Field(None, description="升级时间")
    is_performance_impact: bool = Field(False, description="是否纳入月度绩效考核")


class AlertEscalationCreate(AlertEscalationBase):
    pass


class AlertEscalationRead(AlertEscalationBase):
    model_config = {"from_attributes": True}


class ExpenseReportBase(BaseModel):
    expense_id: str = Field(..., max_length=20, description="报销单号")
    applicant_id: str = Field(..., max_length=20, description="申请人ID")
    budget_id: str = Field(..., max_length=20, description="关联预算ID")
    l1_code: str = Field(..., max_length=2, description="费用L1科目")
    l2_code: Optional[str] = Field(None, max_length=5, description="费用L2科目")
    l3_code: Optional[str] = Field(None, max_length=10, description="费用L3科目")
    amount: float = Field(..., description="报销金额")
    description: Optional[str] = Field(None, description="报销说明")
    control_tag: Optional[ControlModeEnum] = Field(None, description="管控标签")
    status: ExpenseStatus = Field(ExpenseStatus.DRAFT, description="报销单状态")
    center_id: Optional[str] = Field(None, max_length=10, description="归属中心")
    department_id: Optional[str] = Field(None, max_length=10, description="归属部门")
    legal_entity_id: Optional[str] = Field(None, max_length=10, description="法人实体ID")


class ExpenseReportCreate(ExpenseReportBase):
    pass


class ExpenseReportRead(ExpenseReportBase):
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    model_config = {"from_attributes": True}


class OrganizationBase(BaseModel):
    org_id: str = Field(..., max_length=10, description="组织ID")
    org_name: str = Field(..., max_length=100, description="组织名称")
    org_type: str = Field(..., max_length=20, description="组织类型")
    parent_id: Optional[str] = Field(None, max_length=10, description="上级组织ID")
    center_id: Optional[str] = Field(None, max_length=10, description="归属中心")


class OrganizationRead(OrganizationBase):
    model_config = {"from_attributes": True}


class RoleBase(BaseModel):
    role_id: str = Field(..., max_length=20, description="角色ID")
    role_name: str = Field(..., max_length=50, description="角色名称")
    role_type: str = Field(..., max_length=30, description="角色类型")
    permissions: Optional[List[str]] = Field(None, description="权限列表")


class RoleRead(RoleBase):
    model_config = {"from_attributes": True}


class StrategicInitiativeBase(BaseModel):
    initiative_id: str = Field(..., max_length=50, description="战略举措编号")
    initiative_name: str = Field(..., max_length=200, description="战略举措名称")
    strategic_intent_l1: StrategicIntentL1 = Field(..., description="战略意图L1(三大战略方向)")
    strategic_intent_l2: str = Field(..., max_length=100, description="战略意图L2(产品线×区域)")
    owner_center: str = Field(..., max_length=20, description="归属中心")
    owner_manager: str = Field(..., max_length=50, description="负责人")
    kpi_target: Optional[float] = Field(None, description="KPI目标值")
    kpi_actual: Optional[float] = Field(None, description="KPI实际值")
    budget_allocated: Optional[float] = Field(None, description="已分配预算")
    status: str = Field("规划中", description="状态")


class StrategicInitiativeCreate(StrategicInitiativeBase):
    pass


class StrategicInitiativeRead(StrategicInitiativeBase):
    created_at: Optional[datetime] = None
    closed_at: Optional[datetime] = None
    model_config = {"from_attributes": True}


class QuarterlyAllocationBase(BaseModel):
    allocation_id: str = Field(..., max_length=50, description="分期编号")
    budget_id: str = Field(..., max_length=20, description="预算项目ID")
    quarter: str = Field(..., description="季度(Q1/Q2/Q3/Q4)")
    planned_amount: float = Field(..., description="计划金额")
    actual_amount: float = Field(0, description="实际金额")
    execution_rate: Optional[float] = Field(None, description="执行率(%)")
    milestone_achieved: str = Field("未达成", description="里程碑达成状态")


class QuarterlyAllocationCreate(QuarterlyAllocationBase):
    pass


class QuarterlyAllocationRead(QuarterlyAllocationBase):
    created_at: Optional[datetime] = None
    model_config = {"from_attributes": True}


class ManagementReportBase(BaseModel):
    report_id: str = Field(..., max_length=50, description="报告编号")
    report_type: str = Field(..., description="报告类型(月度快报/季度汇报/年度复盘)")
    report_period: str = Field(..., max_length=10, description="报告期")
    budget_execution_rate: Optional[float] = Field(None, description="预算执行率(%)")
    alert_closure_rate: Optional[float] = Field(None, description="预警闭环率(%)")
    strategic_intent_execution: Optional[str] = Field(None, description="战略意图执行情况(JSON)")
    gap_analysis: Optional[str] = Field(None, description="GAP分析(JSON)")
    issue_list: Optional[str] = Field(None, description="问题清单(JSON)")
    data_version: str = Field("草稿", description="数据版本(草稿/已定稿)")
    status: str = Field("草稿", description="状态(草稿/已发布/已归档)")


class ManagementReportCreate(ManagementReportBase):
    pass


class ManagementReportRead(ManagementReportBase):
    locked_at: Optional[datetime] = None
    published_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    model_config = {"from_attributes": True}


class APIResponse(BaseModel):
    success: bool = True
    message: str = "ok"
    data: Optional[Any] = None


class APIPageResponse(BaseModel):
    success: bool = True
    message: str = "ok"
    total: int = 0
    page: int = 1
    page_size: int = 20
    data: List[Any] = []
