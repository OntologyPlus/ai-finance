from sqlalchemy import Column, String, Enum, Numeric, DateTime, Text, func
from models.database import Base


class StrategicInitiative(Base):
    __tablename__ = "t_strategic_initiative"

    initiative_id = Column(String(50), primary_key=True, comment="战略举措编号")
    initiative_name = Column(String(200), nullable=False, comment="战略举措名称")
    strategic_intent_l1 = Column(
        Enum("全渠道商业化", "创新研发", "国际化", name="si_intent_l1_enum"),
        nullable=False,
        comment="战略意图L1(三大战略方向)",
    )
    strategic_intent_l2 = Column(String(100), nullable=False, comment="战略意图L2(产品线×区域)")
    owner_center = Column(String(20), nullable=False, comment="归属中心")
    owner_manager = Column(String(50), nullable=False, comment="负责人")
    kpi_target = Column(Numeric(15, 2), nullable=True, comment="KPI目标值")
    kpi_actual = Column(Numeric(15, 2), nullable=True, comment="KPI实际值")
    budget_allocated = Column(Numeric(15, 2), nullable=True, comment="已分配预算")
    status = Column(
        Enum("规划中", "执行中", "已完成", "已终止", name="si_status_enum"),
        nullable=False,
        default="规划中",
        comment="状态",
    )
    created_at = Column(DateTime, server_default=func.now(), comment="创建时间")
    closed_at = Column(DateTime, nullable=True, comment="关闭时间")


class QuarterlyAllocation(Base):
    __tablename__ = "t_quarterly_allocation"

    allocation_id = Column(String(50), primary_key=True, comment="分期编号")
    budget_id = Column(String(20), nullable=False, comment="预算项目ID")
    quarter = Column(
        Enum("Q1", "Q2", "Q3", "Q4", name="qa_quarter_enum"),
        nullable=False,
        comment="季度",
    )
    planned_amount = Column(Numeric(15, 2), nullable=False, comment="计划金额")
    actual_amount = Column(Numeric(15, 2), nullable=False, default=0, comment="实际金额")
    execution_rate = Column(Numeric(5, 2), nullable=True, comment="执行率(%)")
    milestone_achieved = Column(
        Enum("未达成", "部分达成", "已达成", name="qa_milestone_enum"),
        nullable=False,
        default="未达成",
        comment="里程碑达成状态",
    )
    created_at = Column(DateTime, server_default=func.now(), comment="创建时间")


class ManagementReport(Base):
    __tablename__ = "t_management_report"

    report_id = Column(String(50), primary_key=True, comment="报告编号")
    report_type = Column(
        Enum("月度快报", "季度汇报", "年度复盘", name="mr_type_enum"),
        nullable=False,
        comment="报告类型",
    )
    report_period = Column(String(10), nullable=False, comment="报告期(如2026-Q1)")
    budget_execution_rate = Column(Numeric(5, 2), nullable=True, comment="预算执行率(%)")
    alert_closure_rate = Column(Numeric(5, 2), nullable=True, comment="预警闭环率(%)")
    strategic_intent_execution = Column(Text, nullable=True, comment="战略意图执行情况(JSON)")
    gap_analysis = Column(Text, nullable=True, comment="GAP分析(JSON)")
    issue_list = Column(Text, nullable=True, comment="问题清单(JSON)")
    data_version = Column(
        Enum("草稿", "已定稿", name="mr_data_version_enum"),
        nullable=False,
        default="草稿",
        comment="数据版本",
    )
    locked_at = Column(DateTime, nullable=True, comment="定稿锁定时间")
    status = Column(
        Enum("草稿", "已发布", "已归档", name="mr_status_enum"),
        nullable=False,
        default="草稿",
        comment="状态",
    )
    published_at = Column(DateTime, nullable=True, comment="发布时间")
    created_at = Column(DateTime, server_default=func.now(), comment="创建时间")
