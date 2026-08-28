from sqlalchemy import Column, String, Numeric, Text, DateTime, ForeignKey, func, Boolean, Integer, JSON
from models.database import Base


class ExecutionRate(Base):
    __tablename__ = "execution_rate"

    id = Column(String(20), primary_key=True, comment="记录ID")
    period = Column(String(10), nullable=False, comment="统计期间(YYYY-MM)")
    l1_code = Column(
        String(2),
        ForeignKey("budget_subject_l1.l1_code"),
        nullable=False,
        comment="L1科目编码",
    )
    l2_code = Column(
        String(5),
        ForeignKey("budget_subject_l2.l2_code"),
        nullable=True,
        comment="L2科目编码",
    )
    l3_code = Column(
        String(10),
        ForeignKey("budget_subject_l3.l3_code"),
        nullable=True,
        comment="L3科目编码",
    )
    center_id = Column(String(10), nullable=True, comment="归属中心")
    monthly_plan = Column(Numeric(15, 2), nullable=True, comment="月度分期计划")
    monthly_actual = Column(Numeric(15, 2), nullable=True, comment="月度实际发生")
    cumulative_plan = Column(Numeric(15, 2), nullable=True, comment="累计分期计划")
    cumulative_actual = Column(Numeric(15, 2), nullable=True, comment="累计实际发生")
    annual_budget = Column(Numeric(15, 2), nullable=True, comment="年度预算")
    monthly_rate = Column(Numeric(5, 2), nullable=True, comment="月度执行率")
    cumulative_rate = Column(Numeric(5, 2), nullable=True, comment="累计执行率")
    annual_rate = Column(Numeric(5, 2), nullable=True, comment="年度执行率")
    is_locked = Column(Boolean, default=False)
    locked_by = Column(String(64), default="")
    locked_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, server_default=func.now(), comment="创建时间")


class GapAnalysis(Base):
    __tablename__ = "gap_analysis"

    id = Column(String(20), primary_key=True, comment="记录ID")
    period = Column(String(10), nullable=False, comment="统计期间(YYYY-QN)")
    center_id = Column(String(10), nullable=True, comment="归属中心")
    l1_code = Column(
        String(2),
        ForeignKey("budget_subject_l1.l1_code"),
        nullable=False,
        comment="L1科目编码",
    )
    gap1 = Column(Numeric(15, 2), nullable=True, comment="GAP1-目标差距")
    gap2 = Column(Numeric(15, 2), nullable=True, comment="GAP2-执行差距")
    gap3 = Column(Numeric(15, 2), nullable=True, comment="GAP3-预测变动")
    gap1_detail = Column(Text, nullable=True, comment="GAP1归因详情(JSON)")
    gap2_detail = Column(Text, nullable=True, comment="GAP2归因详情(JSON)")
    gap3_detail = Column(Text, nullable=True, comment="GAP3归因详情(JSON)")
    created_at = Column(DateTime, server_default=func.now(), comment="创建时间")


class ListAnalysis(Base):
    __tablename__ = "list_analysis"

    id = Column(String(20), primary_key=True, comment="记录ID")
    period = Column(String(10), nullable=False, comment="统计期间(YYYY-QN)")
    center_id = Column(String(10), nullable=True, comment="归属中心")
    list_type = Column(String(10), nullable=False, comment="List类型(List1/List2/List3)")
    item_name = Column(String(200), nullable=False, comment="项目名称")
    l1_code = Column(
        String(2),
        ForeignKey("budget_subject_l1.l1_code"),
        nullable=True,
        comment="L1科目编码",
    )
    amount = Column(Numeric(15, 2), nullable=True, comment="金额")
    description = Column(Text, nullable=True, comment="说明")
    action_plan = Column(Text, nullable=True, comment="行动计划")
    created_at = Column(DateTime, server_default=func.now(), comment="创建时间")


class MonthlyReport(Base):
    __tablename__ = "monthly_report"

    id = Column(String(20), primary_key=True, comment="报告ID")
    period = Column(String(10), nullable=False, comment="报告期间(YYYY-MM)")
    report_type = Column(String(30), nullable=False, comment="报告类型(月度快报/季度汇报/年度复盘/经营分析会)")
    center_id = Column(String(10), nullable=True, comment="编制中心")
    content = Column(Text, nullable=True, comment="报告内容(JSON)")
    file_path = Column(String(500), nullable=True, comment="报告文件路径")
    status = Column(String(20), nullable=False, default="编制中", comment="报告状态")
    finalized_at = Column(DateTime, nullable=True, comment="定稿时间")
    created_at = Column(DateTime, server_default=func.now(), comment="创建时间")
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), comment="更新时间")


# ───── 9 张经营诊断卡模型（v1.0 新增） ─────

class DiagnosisCard(Base):
    """诊断卡（卡1-9）"""
    __tablename__ = "diagnosis_card"

    id = Column(String(32), primary_key=True, comment="诊断卡ID")
    period = Column(String(7), nullable=False, index=True, comment="诊断期间(YYYY-MM)")
    card_type = Column(String(32), nullable=False, index=True, comment="卡类型：revenue_health/gross_margin/expense_pacing/product_mix/channel_split/profit_authenticity/commercialization_efficiency/policy_risk/cashflow_quality")
    card_number = Column(Integer, nullable=False, comment="卡编号 1-9")
    card_name = Column(String(64), nullable=False, comment="卡名称")
    signal_light = Column(String(8), nullable=False, default="green", comment="信号灯：red/yellow/green")
    light_reason = Column(Text, nullable=True, comment="信号灯判定原因")

    judgment = Column(Text, nullable=True, comment="核心判断（AI生成，50字内）")
    evidence = Column(Text, nullable=True, comment="数据证据（100字内）")
    root_cause = Column(Text, nullable=True, comment="根因分析（150字内）")
    actions = Column(Text, nullable=True, comment="行动建议（100字内）")
    pending_question = Column(Text, nullable=True, comment="待业务负责人确认的问题")

    metrics_json = Column(JSON, nullable=True, comment="完整数据切片")
    threshold_json = Column(JSON, nullable=True, comment="实际阈值与规则")
    framework_ref = Column(String(50), nullable=True, comment="引用的分析框架")
    ai_quality_level = Column(String(8), nullable=True, comment="AI文字质量等级 L1-L4")
    ai_review_passed = Column(Boolean, default=False, comment="AI Self-Reflection是否通过")

    generated_at = Column(DateTime, server_default=func.now(), comment="生成时间")
    reviewed_by = Column(String(64), nullable=True, comment="人工review人")
    reviewed_at = Column(DateTime, nullable=True, comment="人工review时间")
    is_approved = Column(Boolean, default=False, comment="是否审核通过")
    created_at = Column(DateTime, server_default=func.now(), comment="创建时间")
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), comment="更新时间")


class DiagnosisReport(Base):
    """诊断报告（4部分+9卡）"""
    __tablename__ = "diagnosis_report"

    id = Column(String(32), primary_key=True, comment="报告ID")
    period = Column(String(7), nullable=False, unique=True, index=True, comment="报告期间(YYYY-MM)")

    # 第一部分：经营全景
    dupont_data = Column(JSON, nullable=True, comment="杜邦瀑布图数据")
    top_judgments = Column(JSON, nullable=True, comment="3-5个核心判断")

    # 第二部分：9 张卡
    card_results = Column(JSON, nullable=True, comment="9 张诊断卡结果")

    # 第三部分：产品组合
    bcg_data = Column(JSON, nullable=True, comment="BCG 矩阵数据")

    # 第四部分：行动建议
    sar_data = Column(JSON, nullable=True, comment="SAR 行动建议")

    rendered_html = Column(Text, nullable=True, comment="完整 HTML 渲染结果")
    markdown_source = Column(Text, nullable=True, comment="Markdown 源")

    status = Column(String(20), nullable=False, default="draft", comment="状态：draft/pending_review/approved/published")
    generated_at = Column(DateTime, server_default=func.now(), comment="生成时间")
    reviewed_by = Column(String(64), nullable=True, comment="审核人")
    reviewed_at = Column(DateTime, nullable=True, comment="审核时间")
    published_at = Column(DateTime, nullable=True, comment="发布时间")
    created_at = Column(DateTime, server_default=func.now(), comment="创建时间")
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), comment="更新时间")


class BudgetHealthScore(Base):
    """预算健康度评分"""
    __tablename__ = "budget_health_score"

    id = Column(String(32), primary_key=True, comment="评分ID")
    period = Column(String(7), nullable=False, index=True, comment="评分期间(YYYY-MM)")

    overall_score = Column(Numeric(5, 2), nullable=False, comment="综合评分 0-100")
    execution_score = Column(Numeric(5, 2), nullable=True, comment="执行率健康度")
    alignment_score = Column(Numeric(5, 2), nullable=True, comment="战略对齐度")
    risk_score = Column(Numeric(5, 2), nullable=True, comment="风险敞口")
    transfer_score = Column(Numeric(5, 2), nullable=True, comment="调拨合理性")
    data_score = Column(Numeric(5, 2), nullable=True, comment="数据完整度")

    dimension_details = Column(JSON, nullable=True, comment="各维度明细")
    risk_factors = Column(JSON, nullable=True, comment="风险因素列表")
    recommendations = Column(JSON, nullable=True, comment="改进建议列表")

    generated_at = Column(DateTime, server_default=func.now(), comment="生成时间")
    created_at = Column(DateTime, server_default=func.now(), comment="创建时间")


class AlertDrillDown(Base):
    """预警根因下钻记录"""
    __tablename__ = "alert_drill_down"

    id = Column(String(32), primary_key=True, comment="下钻ID")
    alert_id = Column(String(32), nullable=False, index=True, comment="预警ID")
    period = Column(String(7), nullable=False, index=True, comment="期间")

    l1_node = Column(String(64), nullable=True, comment="L1科目层")
    l2_node = Column(String(64), nullable=True, comment="L2子科目层")
    center_node = Column(String(64), nullable=True, comment="中心层")
    trend_node = Column(Text, nullable=True, comment="季度趋势")
    peer_node = Column(Text, nullable=True, comment="同类对比")

    cascade_risk = Column(JSON, nullable=True, comment="级联风险评估")
    ai_root_cause = Column(Text, nullable=True, comment="AI生成的根因")

    generated_at = Column(DateTime, server_default=func.now(), comment="生成时间")
    created_at = Column(DateTime, server_default=func.now(), comment="创建时间")


class ProactiveInsight(Base):
    """主动建议洞察记录"""
    __tablename__ = "proactive_insight"

    id = Column(String(32), primary_key=True, comment="洞察ID")
    user_id = Column(String(64), nullable=True, index=True, comment="目标用户")
    period = Column(String(7), nullable=True, comment="触发期间")

    insight_type = Column(String(32), nullable=False, index=True, comment="洞察类型：diagnosis_red/budget_overrun/alert_timeout/report_pending/decision_sla")
    priority = Column(String(16), nullable=False, default="info", comment="优先级：critical/attention/info")
    title = Column(String(200), nullable=False, comment="标题")
    detail = Column(Text, nullable=True, comment="详情")
    action_label = Column(String(64), nullable=True, comment="操作按钮文字")
    action_url = Column(String(500), nullable=True, comment="操作跳转URL")
    related_object = Column(String(64), nullable=True, comment="关联对象ID")

    is_read = Column(Boolean, default=False, comment="是否已读")
    is_dismissed = Column(Boolean, default=False, comment="是否已忽略")
    created_at = Column(DateTime, server_default=func.now(), comment="创建时间")
