from __future__ import annotations
from sqlalchemy import Column, DateTime, Float, Integer, String, Text, JSON, func
from models.database import Base


class CostCenter(Base):
    __tablename__ = "cost_centers"
    id = Column(Integer, primary_key=True, autoincrement=True)
    center_code = Column(String(50), unique=True, nullable=False, comment="成本中心编码")
    center_name = Column(String(200), nullable=False, comment="中心名称")
    center_type = Column(String(20), default="成本", comment="成本/利润/投资/收入")
    manager = Column(String(100), comment="负责人")
    parent_center_id = Column(Integer, comment="上级成本中心ID")
    status = Column(String(20), default="活跃")
    created_at = Column(DateTime, server_default=func.now())


class StandardCost(Base):
    __tablename__ = "standard_costs"
    id = Column(Integer, primary_key=True, autoincrement=True)
    cost_center_id = Column(Integer, nullable=False, comment="成本中心ID")
    cost_item = Column(String(200), nullable=False, comment="成本项目")
    standard_quantity = Column(Float, default=0, comment="标准用量")
    standard_price = Column(Float, default=0, comment="标准单价")
    standard_total = Column(Float, default=0, comment="标准成本总额")
    effective_from = Column(DateTime, comment="生效日期")
    created_at = Column(DateTime, server_default=func.now())


class CostAllocation(Base):
    __tablename__ = "cost_allocations"
    id = Column(Integer, primary_key=True, autoincrement=True)
    rule_name = Column(String(200), nullable=False, comment="分摊规则名称")
    source_center_id = Column(Integer, comment="源成本中心ID")
    allocation_basis = Column(String(50), comment="分摊基准(人数/面积/收入比例)")
    allocation_ratios = Column(JSON, default=dict, comment="分摊比例{center_id: ratio}")
    period = Column(String(10), comment="期间")
    total_amount = Column(Float, default=0, comment="分摊总金额")
    created_at = Column(DateTime, server_default=func.now())


class InternalSettlement(Base):
    __tablename__ = "internal_settlements"
    id = Column(Integer, primary_key=True, autoincrement=True)
    provider_id = Column(Integer, nullable=False, comment="提供方成本中心ID")
    consumer_id = Column(Integer, nullable=False, comment="使用方成本中心ID")
    service_description = Column(String(500), comment="服务描述")
    service_volume = Column(Float, default=0, comment="服务量")
    transfer_price = Column(Float, default=0, comment="内部转移价格")
    settlement_amount = Column(Float, default=0, comment="结算金额")
    status = Column(String(20), default="待结算", comment="待结算/已结算/已驳回")
    period = Column(String(10), comment="期间")
    created_at = Column(DateTime, server_default=func.now())
