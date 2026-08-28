from sqlalchemy import Column, String, Enum, Text, Boolean, Integer, Numeric, DateTime, ForeignKey, func
from models.database import Base


class AlertRecord(Base):
    __tablename__ = "alert_record"

    alert_id = Column(String(20), primary_key=True, comment="预警编号")
    alert_level = Column(
        Enum("蓝色", "黄色", "橙色", "红色", name="alert_level_enum"),
        nullable=False,
        comment="预警级别",
    )
    alert_type = Column(
        Enum("月度执行进度", "季度滚动预测", "里程碑", "L1专项", "实时核销预警", "实时冻结预警", "实时释放预警", "实时授予预警", "实时事件预警", "预测超支", "资源闲置", "战略维度", "B类膨胀预警", name="alert_type_enum"),
        nullable=False,
        comment="预警类型",
    )
    alert_status = Column(
        Enum("开放", "响应中", "待闭环确认", "已闭环", "已升级", "待解决", name="alert_status_enum"),
        nullable=False,
        default="开放",
        comment="预警状态",
    )
    l1_code = Column(
        String(2),
        ForeignKey("budget_subject_l1.l1_code"),
        nullable=True,
        comment="关联L1科目",
    )
    l2_code = Column(
        String(5),
        ForeignKey("budget_subject_l2.l2_code"),
        nullable=True,
        comment="关联L2科目",
    )
    l3_code = Column(
        String(10),
        ForeignKey("budget_subject_l3.l3_code"),
        nullable=True,
        comment="关联L3科目",
    )
    budget_id = Column(
        String(20),
        ForeignKey("budget_item.budget_id"),
        nullable=True,
        comment="关联预算ID",
    )
    project_id = Column(String(20), nullable=True, comment="关联项目ID")
    trigger_value = Column(Numeric(15, 2), nullable=True, comment="触发值")
    threshold_value = Column(Numeric(15, 2), nullable=True, comment="阈值")
    deviation_rate = Column(Numeric(5, 2), nullable=True, comment="偏离率(%)")
    responsible_person = Column(String(50), nullable=True, comment="责任人")
    response_deadline = Column(DateTime, nullable=True, comment="响应截止时间")
    response_hours = Column(Integer, nullable=True, comment="响应时限（小时）")
    notification_targets = Column(Text, nullable=True, comment="通知对象列表(JSON)")
    created_at = Column(DateTime, server_default=func.now(), comment="预警创建时间")
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), comment="最后更新时间")


class AlertClosure(Base):
    __tablename__ = "alert_closure"

    closure_id = Column(String(20), primary_key=True, comment="闭环档案编号")
    alert_id = Column(
        String(20),
        ForeignKey("alert_record.alert_id"),
        nullable=False,
        comment="预警编号",
    )
    business_response = Column(Text, nullable=True, comment="业务单元整改方案")
    business_responder = Column(String(50), nullable=True, comment="业务响应人")
    business_response_at = Column(DateTime, nullable=True, comment="业务响应时间")
    bp_confirmation = Column(Text, nullable=True, comment="财经BP确认意见")
    bp_confirmer = Column(String(50), nullable=True, comment="财经BP确认人")
    bp_confirmation_at = Column(DateTime, nullable=True, comment="BP确认时间")
    closure_status = Column(
        Enum("待业务响应", "待BP确认", "已闭环", "已驳回", name="closure_status_enum"),
        nullable=False,
        default="待业务响应",
        comment="闭环状态",
    )
    retention_period = Column(Integer, nullable=False, default=3, comment="存档年限（≥3年）")
    created_at = Column(DateTime, server_default=func.now(), comment="创建时间")


class AlertEscalation(Base):
    __tablename__ = "alert_escalation"

    escalation_id = Column(String(20), primary_key=True, comment="升级记录编号")
    alert_id = Column(
        String(20),
        ForeignKey("alert_record.alert_id"),
        nullable=False,
        comment="预警编号",
    )
    escalation_reason = Column(
        Enum("超时未响应", "超时未闭环", name="escalation_reason_enum"),
        nullable=False,
        comment="升级原因",
    )
    escalation_level = Column(String(50), nullable=True, comment="升级通知对象级别")
    escalation_target = Column(String(50), nullable=True, comment="升级通知目标人")
    original_deadline = Column(DateTime, nullable=True, comment="原响应截止时间")
    escalation_at = Column(DateTime, nullable=True, comment="升级时间")
    is_performance_impact = Column(Boolean, nullable=False, default=False, comment="是否纳入月度绩效考核")
