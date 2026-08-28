from sqlalchemy import Column, String, Text, Integer, DateTime, func
from models.database import Base


class CaliberMapping(Base):
    """财务口径 ↔ 管理口径 映射配置"""
    __tablename__ = "caliber_mapping"

    mapping_id = Column(String(20), primary_key=True, comment="映射ID")
    financial_code = Column(String(20), nullable=False, comment="财务科目代码")
    financial_name = Column(String(100), nullable=False, comment="财务科目名称")
    management_code = Column(String(20), nullable=False, comment="管理维度代码")
    management_name = Column(String(100), nullable=False, comment="管理维度名称")
    conversion_rule = Column(String(50), default="1:1", comment="转换规则(1:1/1:N/N:1)")
    adjustment_formula = Column(Text, comment="调整公式(如: +资本化利息)")
    difference_note = Column(Text, comment="口径差异说明")
    sort_order = Column(Integer, default=0, comment="排序")


class CaliberDifference(Base):
    """口径差异记录"""
    __tablename__ = "caliber_difference"

    diff_id = Column(String(20), primary_key=True, comment="差异ID")
    period = Column(String(7), nullable=False, comment="期间 YYYY-MM")
    l1_code = Column(String(10), nullable=False, comment="L1科目代码")
    financial_amount = Column(Integer, default=0, comment="财务口径金额(分)")
    management_amount = Column(Integer, default=0, comment="管理口径金额(分)")
    difference_amount = Column(Integer, default=0, comment="差异金额(分)")
    difference_reason = Column(Text, comment="差异原因")
