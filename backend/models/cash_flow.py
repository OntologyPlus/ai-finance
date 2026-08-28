from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import Column, DateTime, Float, Integer, String, Text, JSON, func

from models.database import Base


class CashFlowPlan(Base):
    __tablename__ = "cash_flow_plans"

    id = Column(Integer, primary_key=True, autoincrement=True)
    period = Column(String(10), nullable=False, comment="计划期 YYYY-MM")
    activity_type = Column(String(20), nullable=False, comment="经营/投资/筹资")
    inflow_amount = Column(Float, default=0, comment="计划流入金额")
    outflow_amount = Column(Float, default=0, comment="计划流出金额")
    net_amount = Column(Float, default=0, comment="计划净额")
    actual_inflow = Column(Float, default=0, comment="实际流入")
    actual_outflow = Column(Float, default=0, comment="实际流出")
    actual_net = Column(Float, default=0, comment="实际净额")
    status = Column(String(20), default="草稿", comment="草稿/已审批/执行中/已结算")
    center_id = Column(String(20), comment="中心ID")
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, onupdate=func.now())


class CashPool(Base):
    __tablename__ = "cash_pools"

    id = Column(Integer, primary_key=True, autoincrement=True)
    pool_name = Column(String(100), nullable=False, comment="资金池名称")
    total_balance = Column(Float, default=0, comment="总余额")
    min_balance = Column(Float, default=0, comment="最低余额")
    alert_threshold = Column(Float, default=0, comment="预警阈值")
    aggregation_rule = Column(JSON, default=dict, comment="归集规则")
    status = Column(String(20), default="活跃")
    created_at = Column(DateTime, server_default=func.now())


class PaymentSchedule(Base):
    __tablename__ = "payment_schedules"

    id = Column(Integer, primary_key=True, autoincrement=True)
    expense_id = Column(String(50), comment="关联报销单号")
    contract_id = Column(String(50), comment="关联合同ID")
    planned_date = Column(DateTime, comment="计划付款日")
    planned_amount = Column(Float, default=0, comment="计划付款金额")
    actual_date = Column(DateTime, comment="实际付款日")
    actual_amount = Column(Float, default=0, comment="实际付款金额")
    status = Column(String(20), default="待付款", comment="待付款/已付款/已逾期/已取消")
    vendor_name = Column(String(200), comment="收款方名称")
    created_at = Column(DateTime, server_default=func.now())


class ReceiptForecast(Base):
    __tablename__ = "receipt_forecasts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    revenue_budget_id = Column(String(50), comment="关联收入预算ID")
    forecast_date = Column(DateTime, comment="预测收款日")
    forecast_amount = Column(Float, default=0, comment="预测收款金额")
    actual_date = Column(DateTime, comment="实际收款日")
    actual_amount = Column(Float, default=0, comment="实际收款金额")
    confidence = Column(Float, default=0.5, comment="预测置信度0-1")
    customer_name = Column(String(200), comment="付款方名称")
    created_at = Column(DateTime, server_default=func.now())
