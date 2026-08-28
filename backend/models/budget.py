from sqlalchemy import Column, String, Enum, Boolean, Text, Numeric, DateTime, ForeignKey, func
from models.database import Base


class BudgetSubjectL1(Base):
    __tablename__ = "budget_subject_l1"

    l1_code = Column(String(2), primary_key=True, comment="L1科目编码")
    l1_name = Column(String(50), nullable=False, comment="L1科目名称")
    management_mode = Column(
        Enum("项目化管理", "通用管控", "合规导向", name="management_mode_enum"),
        nullable=False,
        comment="管控模式",
    )
    alert_rule_type = Column(
        Enum("通用规则", "通用+专项", name="alert_rule_type_enum"),
        nullable=False,
        comment="预警规则类型",
    )
    has_l2 = Column(Boolean, nullable=False, default=False, comment="是否含L2子类")
    description = Column(Text, nullable=True, comment="自然语言定义")
    created_at = Column(DateTime, server_default=func.now(), comment="创建时间")
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), comment="更新时间")


class BudgetSubjectL2(Base):
    __tablename__ = "budget_subject_l2"

    l2_code = Column(String(5), primary_key=True, comment="L2科目编码")
    l2_name = Column(String(100), nullable=False, comment="L2科目名称")
    l1_code = Column(
        String(2),
        ForeignKey("budget_subject_l1.l1_code"),
        nullable=False,
        comment="归属L1编码",
    )
    special_rules = Column(Text, nullable=True, comment="特殊规则")
    roi_threshold = Column(String(200), nullable=True, comment="ROI预警阈值")
    created_at = Column(DateTime, server_default=func.now(), comment="创建时间")
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), comment="更新时间")


class BudgetSubjectL3(Base):
    __tablename__ = "budget_subject_l3"

    l3_code = Column(String(10), primary_key=True, comment="L3科目编码")
    l3_name = Column(String(100), nullable=False, comment="L3科目名称")
    l2_code = Column(
        String(5),
        ForeignKey("budget_subject_l2.l2_code"),
        nullable=True,
        comment="归属L2编码",
    )
    l1_code = Column(
        String(2),
        ForeignKey("budget_subject_l1.l1_code"),
        nullable=False,
        comment="归属L1编码",
    )
    control_tag = Column(
        Enum("强管控", "中心弱管控", "组合管控", "不管控", name="control_tag_enum"),
        nullable=False,
        comment="管控级别标签",
    )
    variety_group = Column(String(20), nullable=True, comment="品种组编码")
    is_project_managed = Column(Boolean, nullable=False, default=False, comment="是否项目化管理")
    alert_rules = Column(Text, nullable=True, comment="适用的预警规则ID列表(JSON)")
    created_at = Column(DateTime, server_default=func.now(), comment="创建时间")
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), comment="更新时间")


class BudgetItem(Base):
    __tablename__ = "budget_item"

    budget_id = Column(String(20), primary_key=True, comment="预算项目唯一标识")
    budget_name = Column(String(200), nullable=False, comment="预算项目名称")
    budget_category = Column(
        Enum("A", "B", name="budget_category_enum"),
        nullable=False,
        comment="A/B类别",
    )
    l1_code = Column(
        String(2),
        ForeignKey("budget_subject_l1.l1_code"),
        nullable=False,
        comment="归属L1科目",
    )
    l2_code = Column(
        String(5),
        ForeignKey("budget_subject_l2.l2_code"),
        nullable=True,
        comment="归属L2科目",
    )
    l3_code = Column(
        String(10),
        ForeignKey("budget_subject_l3.l3_code"),
        nullable=True,
        comment="归属L3科目",
    )
    quadrant = Column(
        Enum("发展", "收缩", "稳定", "探索", name="quadrant_enum"),
        nullable=False,
        comment="象限归属",
    )
    strategy_initiative_id = Column(String(20), nullable=True, comment="对标战略举措编号")
    annual_amount = Column(Numeric(15, 2), nullable=False, default=0, comment="年度预算总额")
    granted_amount = Column(Numeric(15, 2), nullable=False, default=0, comment="已授予额度")
    frozen_amount = Column(Numeric(15, 2), nullable=False, default=0, comment="已冻结额度")
    used_amount = Column(Numeric(15, 2), nullable=False, default=0, comment="已使用额度")
    available_amount = Column(Numeric(15, 2), nullable=False, default=0, comment="可用额度")
    grant_percentage = Column(Numeric(5, 2), nullable=False, default=0, comment="授予比例")
    status = Column(
        Enum("编制中", "待审批", "审批中", "已授予", "已驳回", "执行中", "已冻结", "已核销", "已取消", name="budget_status_enum"),
        nullable=False,
        default="编制中",
        comment="预算项目状态",
    )
    center_id = Column(String(10), nullable=True, comment="归属中心")
    department_id = Column(String(10), nullable=True, comment="归属部门")
    project_id = Column(String(20), nullable=True, comment="关联项目ID")
    pending_project_budget_id = Column(String(20), nullable=True, comment="暂存项目预算ID(B类专用)")
    strategic_intent_l1 = Column(
        Enum("全渠道商业化", "创新研发", "国际化", name="strategic_intent_l1_enum"),
        nullable=True,
        comment="战略意图L1(三大战略方向)",
    )
    strategic_intent_l2 = Column(String(100), nullable=True, comment="战略意图L2(产品线×区域)")
    product_line = Column(String(50), nullable=True, comment="产品线")
    region = Column(String(50), nullable=True, comment="区域")
    product_variety = Column(String(128), default="")
    channel = Column(String(128), default="")
    created_at = Column(DateTime, server_default=func.now(), comment="创建时间")
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), comment="更新时间")


class B2AConversion(Base):
    __tablename__ = "b2a_conversion"

    conversion_id = Column(String(20), primary_key=True, comment="转换记录编号")
    budget_id = Column(
        String(20),
        ForeignKey("budget_item.budget_id"),
        nullable=False,
        comment="预算项目ID",
    )
    conversion_date = Column(DateTime, nullable=False, comment="转换日期")
    milestone_evidence = Column(Text, nullable=True, comment="里程碑达标证据")
    milestone_period = Column(
        Enum("Q1", "Q2", "Q3", "Q4", name="milestone_period_enum"),
        nullable=False,
        comment="里程碑验证季度",
    )
    approver = Column(String(50), nullable=True, comment="审批人")
    approval_status = Column(
        Enum("待审批", "已通过", "已驳回", name="b2a_approval_status_enum"),
        nullable=False,
        default="待审批",
        comment="审批状态",
    )
    pre_category = Column(
        Enum("B", name="b2a_pre_category_enum"),
        nullable=False,
        default="B",
        comment="转换前类别",
    )
    post_category = Column(
        Enum("A", name="b2a_post_category_enum"),
        nullable=False,
        default="A",
        comment="转换后类别",
    )
    frozen_amount = Column(Numeric(15, 2), nullable=True, comment="转换后冻结额度")
    report_to_committee = Column(Boolean, nullable=False, default=False, comment="是否已向管委会提交专项报告")
    created_at = Column(DateTime, server_default=func.now(), comment="创建时间")


class ControlMode(Base):
    __tablename__ = "control_mode"

    mode = Column(String(20), primary_key=True, comment="管控模式名称")
    code = Column(String(20), nullable=False, unique=True, comment="管控模式编码")
    cross_dept_allowed = Column(Boolean, nullable=False, default=False, comment="可否跨部门")
    cross_category_allowed = Column(Boolean, nullable=False, default=False, comment="可否跨费用类别")
    cross_variety_group_allowed = Column(Boolean, nullable=False, default=False, comment="可否跨品种组")
    over_budget_action = Column(String(100), nullable=False, comment="超预算处理")
    description = Column(Text, nullable=True, comment="描述")
