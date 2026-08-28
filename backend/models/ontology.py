from sqlalchemy import Column, String, Numeric, Text, Boolean, DateTime, ForeignKey, JSON, Integer, func
from models.database import Base


class OntologyObject(Base):
    __tablename__ = "ontology_object"

    object_id = Column(String(30), primary_key=True, comment="对象ID")
    object_name = Column(String(100), nullable=False, comment="对象名称")
    object_type = Column(String(30), nullable=False, comment="对象类别(战略/预算/支出/预警/角色/报表/工具)")
    natural_language_def = Column(Text, nullable=True, comment="自然语言定义")
    key_attributes = Column(Text, nullable=True, comment="关键属性(JSON)")
    participating_relations = Column(Text, nullable=True, comment="参与的关系(JSON)")
    is_active = Column(Boolean, nullable=False, default=True, comment="是否启用")
    created_at = Column(DateTime, server_default=func.now(), comment="创建时间")
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), comment="更新时间")


class OntologyRelation(Base):
    __tablename__ = "ontology_relation"

    relation_id = Column(String(30), primary_key=True, comment="关系ID")
    relation_name = Column(String(50), nullable=False, comment="关系名称")
    source_object_id = Column(
        String(30),
        ForeignKey("ontology_object.object_id"),
        nullable=False,
        comment="源对象ID",
    )
    target_object_id = Column(
        String(30),
        ForeignKey("ontology_object.object_id"),
        nullable=False,
        comment="目标对象ID",
    )
    scene_condition = Column(Text, nullable=True, comment="场景条件")
    semantic_description = Column(Text, nullable=True, comment="语义说明")
    cardinality = Column(String(10), nullable=False, default="N:1", comment="基数约束(N:1/1:N/1:1/N:N)")
    confidence = Column(Numeric(3, 2), nullable=False, default=1.0, comment="关系置信度(1.0=确定)")
    provenance = Column(String(20), nullable=False, default="人工录入", comment="数据来源(人工录入/系统推断/外部导入)")
    is_bidirectional = Column(Boolean, nullable=False, default=False, comment="是否双向关系")
    reverse_relation_id = Column(String(30), nullable=True, comment="反向关系ID")
    is_active = Column(Boolean, nullable=False, default=True, comment="是否启用")
    created_at = Column(DateTime, server_default=func.now(), comment="创建时间")


class OntologyBehavior(Base):
    __tablename__ = "ontology_behavior"

    behavior_id = Column(String(60), primary_key=True, comment="行为ID")
    behavior_name = Column(String(100), nullable=False, comment="行为名称")
    preconditions = Column(Text, nullable=True, comment="前置条件")
    effects = Column(Text, nullable=True, comment="效果")
    parameters = Column(Text, nullable=True, comment="参数(JSON)")
    stage = Column(String(20), nullable=True, comment="所属阶段")
    is_active = Column(Boolean, nullable=False, default=True, comment="是否启用")
    created_at = Column(DateTime, server_default=func.now(), comment="创建时间")
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), comment="更新时间")


class OntologyRule(Base):
    __tablename__ = "ontology_rule"

    rule_id = Column(String(30), primary_key=True, comment="规则ID")
    rule_name = Column(String(100), nullable=False, comment="规则名称")
    rule_type = Column(String(10), nullable=False, comment="规则类型(硬规则/软规则/推理规则)")
    condition = Column(Text, nullable=False, comment="条件")
    result = Column(Text, nullable=False, comment="结果")
    scene_tags = Column(Text, nullable=True, comment="场景标签(JSON)")
    referenced_objects = Column(Text, nullable=True, comment="引用对象(JSON)")
    example = Column(Text, nullable=True, comment="解好的示例")
    is_active = Column(Boolean, nullable=False, default=True, comment="是否启用")
    created_at = Column(DateTime, server_default=func.now(), comment="创建时间")
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), comment="更新时间")


class OntologyScene(Base):
    __tablename__ = "ontology_scene"

    scene_id = Column(String(30), primary_key=True, comment="场景ID")
    scene_name = Column(String(100), nullable=False, comment="场景名称")
    description = Column(Text, nullable=True, comment="场景描述")
    activation_condition = Column(Text, nullable=True, comment="激活条件")
    activated_objects = Column(Text, nullable=True, comment="激活对象(JSON)")
    activated_relations = Column(Text, nullable=True, comment="激活关系(JSON)")
    activated_rules = Column(Text, nullable=True, comment="激活规则(JSON)")
    activated_behaviors = Column(Text, nullable=True, comment="激活行为(JSON)")
    corresponding_stage = Column(String(20), nullable=True, comment="对应阶段")
    is_active = Column(Boolean, nullable=False, default=True, comment="是否启用")
    created_at = Column(DateTime, server_default=func.now(), comment="创建时间")
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), comment="更新时间")


class ReasoningTrace(Base):
    __tablename__ = "reasoning_trace"

    trace_id = Column(String(30), primary_key=True, comment="推理轨迹ID")
    scene_id = Column(
        String(30),
        ForeignKey("ontology_scene.scene_id"),
        nullable=True,
        comment="关联场景ID",
    )
    scene_name = Column(String(100), nullable=True, comment="场景名称")
    input_data = Column(Text, nullable=True, comment="输入数据(JSON)")
    steps = Column(Text, nullable=True, comment="推理步骤(JSON)")
    conclusion = Column(String(2000), nullable=True, comment="最终结论")
    confidence = Column(Numeric(5, 2), nullable=True, comment="置信度")
    rule_ids = Column(Text, nullable=True, comment="匹配规则ID列表(JSON)")
    elapsed_ms = Column(Integer, nullable=True, comment="推理耗时(毫秒)")
    created_at = Column(DateTime, server_default=func.now(), comment="创建时间")


class OntologyObjectInstance(Base):
    """本体对象实例 — 运行时对象实例持久化"""
    __tablename__ = "ontology_object_instance"

    instance_id = Column(String(50), primary_key=True, comment="实例ID，如 BUD-2024-001")
    type_id = Column(String(30), ForeignKey("ontology_object.object_id"), nullable=False, comment="对象类型ID")
    attributes = Column(JSON, nullable=True, comment="属性值(JSON)")
    status = Column(String(30), nullable=False, default="active", comment="生命周期当前状态")
    tenant_id = Column(String(50), nullable=True, comment="多租户ID(预留)")
    created_at = Column(DateTime, server_default=func.now(), comment="创建时间")
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), comment="更新时间")


class OntologyRelationInstance(Base):
    """本体关系实例 — 运行时关系实例持久化"""
    __tablename__ = "ontology_relation_instance"

    instance_id = Column(String(50), primary_key=True, comment="关系实例ID")
    type_id = Column(String(30), ForeignKey("ontology_relation.relation_id"), nullable=False, comment="关系类型ID")
    source_instance_id = Column(String(50), ForeignKey("ontology_object_instance.instance_id"), nullable=False, comment="源实例ID")
    target_instance_id = Column(String(50), ForeignKey("ontology_object_instance.instance_id"), nullable=False, comment="目标实例ID")
    attributes = Column(JSON, nullable=True, comment="属性值(JSON)")
    valid_from = Column(DateTime, nullable=True, comment="生效时间")
    valid_to = Column(DateTime, nullable=True, comment="失效时间")
    created_at = Column(DateTime, server_default=func.now(), comment="创建时间")


class OntologyEventRecord(Base):
    """本体事件记录 — 领域事件持久化"""
    __tablename__ = "ontology_event_record"

    event_id = Column(String(60), primary_key=True, comment="事件ID")
    event_type = Column(String(50), nullable=False, index=True, comment="事件类型，如 object.created")
    source = Column(String(100), nullable=True, comment="发布模块")
    payload = Column(JSON, nullable=True, comment="事件负载(JSON)")
    correlation_id = Column(String(60), nullable=True, index=True, comment="关联ID，用于追踪相关事件")
    created_at = Column(DateTime, server_default=func.now(), index=True, comment="创建时间")


class OntologyVersionSnapshot(Base):
    """本体版本快照 — 变更管理持久化"""
    __tablename__ = "ontology_version_snapshot"

    version_id = Column(String(30), primary_key=True, comment="版本ID，如 ONT-V0001")
    version_number = Column(Integer, nullable=False, comment="版本号")
    change_id = Column(String(50), nullable=True, comment="变更ID")
    snapshot = Column(JSON, nullable=True, comment="完整快照(JSON)")
    snapshot_hash = Column(String(64), nullable=True, comment="SHA256完整性校验")
    is_current = Column(Boolean, nullable=False, default=False, comment="是否当前版本")
    created_at = Column(DateTime, server_default=func.now(), comment="创建时间")


class OntologyConsistencyIssue(Base):
    """本体一致性检查结果"""
    __tablename__ = "ontology_consistency_issue"

    id = Column(Integer, primary_key=True, autoincrement=True, comment="自增ID")
    severity = Column(String(20), nullable=False, index=True, comment="严重度: CRITICAL/HIGH/MEDIUM/LOW")
    category = Column(String(50), nullable=False, comment="检查类别")
    message = Column(Text, nullable=False, comment="问题描述")
    target_id = Column(String(50), nullable=True, comment="目标ID")
    suggestion = Column(Text, nullable=True, comment="修复建议")
    checked_at = Column(DateTime, server_default=func.now(), comment="检查时间")
