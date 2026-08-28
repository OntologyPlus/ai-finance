from __future__ import annotations
from sqlalchemy import Column, DateTime, Float, Integer, String, Text, JSON, func
from models.database import Base


class Pipeline(Base):
    __tablename__ = "pipelines"
    id = Column(Integer, primary_key=True, autoincrement=True)
    pipeline_id = Column(String(50), unique=True, nullable=False, comment="管线编号")
    name = Column(String(200), nullable=False, comment="管线名称")
    indication = Column(String(200), comment="适应症")
    current_stage = Column(String(20), default="发现", comment="当前阶段")
    go_nogo_status = Column(String(20), default="待评估", comment="Go/No-Go状态")
    estimated_launch_date = Column(DateTime, comment="预计上市时间")
    total_budget = Column(Float, default=0, comment="总预算")
    consumed_budget = Column(Float, default=0, comment="已消耗预算")
    status = Column(String(20), default="活跃", comment="活跃/已终止/已暂停")
    created_at = Column(DateTime, server_default=func.now())


class RnDProject(Base):
    __tablename__ = "rnd_projects"
    id = Column(Integer, primary_key=True, autoincrement=True)
    project_id = Column(String(50), unique=True, nullable=False, comment="项目编号")
    name = Column(String(200), nullable=False, comment="项目名称")
    pipeline_id = Column(String(50), comment="所属管线编号")
    project_type = Column(String(50), comment="项目类型")
    manager = Column(String(100), comment="项目经理")
    finance_budget = Column(Float, default=0, comment="财务口径预算")
    management_budget = Column(Float, default=0, comment="管理口径预算")
    consumed_finance = Column(Float, default=0, comment="已消耗财务口径")
    consumed_management = Column(Float, default=0, comment="已消耗管理口径")
    status = Column(String(20), default="进行中")
    created_at = Column(DateTime, server_default=func.now())


class RnDMilestone(Base):
    __tablename__ = "rnd_milestones"
    id = Column(Integer, primary_key=True, autoincrement=True)
    project_id = Column(String(50), nullable=False, comment="所属项目编号")
    name = Column(String(200), nullable=False, comment="里程碑名称")
    planned_date = Column(DateTime, comment="计划完成日")
    actual_date = Column(DateTime, comment="实际完成日")
    status = Column(String(20), default="待完成", comment="待完成/已完成/已延期")
    cro_payment_id = Column(String(50), comment="关联CRO付款ID")
    created_at = Column(DateTime, server_default=func.now())


class ClinicalTrial(Base):
    __tablename__ = "clinical_trials"
    id = Column(Integer, primary_key=True, autoincrement=True)
    trial_id = Column(String(50), unique=True, nullable=False, comment="试验编号")
    name = Column(String(200), nullable=False, comment="试验名称")
    phase = Column(String(20), comment="试验阶段(I/II/III期)")
    cro_vendor = Column(String(200), comment="CRO供应商")
    center_count = Column(Integer, default=0, comment="中心数量")
    total_cost = Column(Float, default=0, comment="总费用")
    allocation_ratios = Column(JSON, default=dict, comment="分摊协议{center: ratio}")
    pipeline_id = Column(String(50), comment="所属管线")
    status = Column(String(20), default="进行中")
    created_at = Column(DateTime, server_default=func.now())
