import uuid
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession
from models.form import FormTemplate

FORM_TEMPLATES = [
    {"id": str(uuid.uuid4())[:64], "form_code": "FM-BUD-001", "form_name": "年度预算申报表(日常)", "form_type": "budget", "category": "budget", "description": "日常费用年度预算申报", "fields": ["科目", "金额", "说明", "战略意图"], "version": 1, "is_active": True},
    {"id": str(uuid.uuid4())[:64], "form_code": "FM-BUD-002", "form_name": "年度预算申报表(项目)", "form_type": "budget", "category": "budget", "description": "项目费用年度预算申报", "fields": ["科目", "金额", "里程碑", "战略意图"], "version": 1, "is_active": True},
    {"id": str(uuid.uuid4())[:64], "form_code": "FM-BUD-003", "form_name": "预算使用申请表(日常)", "form_type": "budget", "category": "budget", "description": "日常费用预算使用申请", "fields": ["科目", "金额", "用途"], "version": 1, "is_active": True},
    {"id": str(uuid.uuid4())[:64], "form_code": "FM-BUD-004", "form_name": "预算使用申请表(项目)", "form_type": "budget", "category": "budget", "description": "项目费用预算使用申请", "fields": ["科目", "金额", "里程碑"], "version": 1, "is_active": True},
    {"id": str(uuid.uuid4())[:64], "form_code": "FM-BUD-005", "form_name": "预算调整申请表", "form_type": "budget", "category": "budget", "description": "预算额度调整申请", "fields": ["调整类型", "调出科目", "调入科目", "金额", "原因"], "version": 1, "is_active": True},
    {"id": str(uuid.uuid4())[:64], "form_code": "FM-BUD-006", "form_name": "B→A转换申请表", "form_type": "budget", "category": "budget", "description": "B类预算转A类预算申请", "fields": ["预算ID", "里程碑证据", "转换金额", "原因"], "version": 1, "is_active": True},
    {"id": str(uuid.uuid4())[:64], "form_code": "FM-EXP-001", "form_name": "费用报销单(日常)", "form_type": "expense", "category": "expense", "description": "日常费用报销", "fields": ["报销人", "部门", "费用日期", "金额", "说明", "科目"], "version": 1, "is_active": True},
    {"id": str(uuid.uuid4())[:64], "form_code": "FM-EXP-002", "form_name": "费用报销单(项目)", "form_type": "expense", "category": "expense", "description": "项目费用报销", "fields": ["报销人", "部门", "费用日期", "金额", "说明", "科目", "项目ID"], "version": 1, "is_active": True},
    {"id": str(uuid.uuid4())[:64], "form_code": "FM-EXP-003", "form_name": "差旅费报销单", "form_type": "expense", "category": "expense", "description": "差旅费用报销", "fields": ["报销人", "部门", "费用日期", "金额", "说明", "出发地", "目的地", "行程", "交通费", "住宿费", "补贴"], "version": 1, "is_active": True},
    {"id": str(uuid.uuid4())[:64], "form_code": "FM-EXP-004", "form_name": "合同付款申请单", "form_type": "expense", "category": "expense", "description": "合同付款申请", "fields": ["报销人", "部门", "费用日期", "金额", "说明", "合同编号", "付款阶段"], "version": 1, "is_active": True},
    {"id": str(uuid.uuid4())[:64], "form_code": "FM-EXP-005", "form_name": "暂支申请单", "form_type": "expense", "category": "expense", "description": "暂支费用申请", "fields": ["报销人", "部门", "费用日期", "金额", "说明", "用途", "预计归还日期"], "version": 1, "is_active": True},
    {"id": str(uuid.uuid4())[:64], "form_code": "FM-EXP-006", "form_name": "发票登记表", "form_type": "expense", "category": "expense", "description": "发票信息登记", "fields": ["报销人", "部门", "费用日期", "金额", "说明", "发票号", "发票类型"], "version": 1, "is_active": True},
    {"id": str(uuid.uuid4())[:64], "form_code": "FM-EXP-007", "form_name": "研发费用报销单(B2)", "form_type": "expense", "category": "expense", "description": "研发费用报销", "fields": ["报销人", "部门", "费用日期", "金额", "说明", "项目编号", "研发阶段", "成果说明"], "version": 1, "is_active": True},
    {"id": str(uuid.uuid4())[:64], "form_code": "FM-EXP-008", "form_name": "差旅费报销单(B3-差旅)", "form_type": "expense", "category": "expense", "description": "差旅费用报销(含行程明细)", "fields": ["报销人", "部门", "费用日期", "金额", "说明", "出发地", "目的地", "行程", "交通费", "住宿费", "补贴"], "version": 1, "is_active": True},
    {"id": str(uuid.uuid4())[:64], "form_code": "FM-EXP-009", "form_name": "咨询服务报销单(B3-咨询)", "form_type": "expense", "category": "expense", "description": "咨询服务费用报销", "fields": ["报销人", "部门", "费用日期", "金额", "说明", "合同编号", "服务期间", "交付物"], "version": 1, "is_active": True},
    {"id": str(uuid.uuid4())[:64], "form_code": "FM-EXP-010", "form_name": "市场推广报销单(B5)", "form_type": "expense", "category": "expense", "description": "市场推广费用报销", "fields": ["报销人", "部门", "费用日期", "金额", "说明", "活动名称", "ROI", "参与人数"], "version": 1, "is_active": True},
    {"id": str(uuid.uuid4())[:64], "form_code": "FM-EXP-011", "form_name": "培训费报销单(B6-培训)", "form_type": "expense", "category": "expense", "description": "培训费用报销", "fields": ["报销人", "部门", "费用日期", "金额", "说明", "培训名称", "参训人", "课时"], "version": 1, "is_active": True},
    {"id": str(uuid.uuid4())[:64], "form_code": "FM-EXP-012", "form_name": "招聘费报销单(B6-招聘)", "form_type": "expense", "category": "expense", "description": "招聘费用报销", "fields": ["报销人", "部门", "费用日期", "金额", "说明", "岗位", "渠道", "候选人数量"], "version": 1, "is_active": True},
    {"id": str(uuid.uuid4())[:64], "form_code": "FM-EXP-013", "form_name": "采购报销单(B7-成品)", "form_type": "expense", "category": "expense", "description": "成品采购费用报销", "fields": ["报销人", "部门", "费用日期", "金额", "说明", "供应商", "品名", "数量", "单价"], "version": 1, "is_active": True},
    {"id": str(uuid.uuid4())[:64], "form_code": "FM-EXP-014", "form_name": "委托加工报销单(B7-委托)", "form_type": "expense", "category": "expense", "description": "委托加工费用报销", "fields": ["报销人", "部门", "费用日期", "金额", "说明", "委托方", "加工内容", "验收标准"], "version": 1, "is_active": True},
    {"id": str(uuid.uuid4())[:64], "form_code": "FM-EXP-015", "form_name": "投资付款申请单(B8)", "form_type": "expense", "category": "expense", "description": "投资付款申请", "fields": ["报销人", "部门", "费用日期", "金额", "说明", "投资标的", "投资阶段", "投资金额"], "version": 1, "is_active": True},
    {"id": str(uuid.uuid4())[:64], "form_code": "FM-EXP-016", "form_name": "利息支付申请单(B9)", "form_type": "expense", "category": "expense", "description": "利息支付申请", "fields": ["报销人", "部门", "费用日期", "金额", "说明", "贷款合同", "利率", "期限"], "version": 1, "is_active": True},
    {"id": str(uuid.uuid4())[:64], "form_code": "FM-EXP-017", "form_name": "固定资产采购报销单(B1-3)", "form_type": "expense", "category": "expense", "description": "固定资产采购报销", "fields": ["报销人", "部门", "费用日期", "金额", "说明", "资产名称", "规格", "使用部门"], "version": 1, "is_active": True},
    {"id": str(uuid.uuid4())[:64], "form_code": "FM-EXP-018", "form_name": "工程付款申请单(B1-2)", "form_type": "expense", "category": "expense", "description": "工程付款申请", "fields": ["报销人", "部门", "费用日期", "金额", "说明", "工程名称", "进度", "验收情况"], "version": 1, "is_active": True},
    {"id": str(uuid.uuid4())[:64], "form_code": "FM-EXP-019", "form_name": "无形资产报销单(B1-1)", "form_type": "expense", "category": "expense", "description": "无形资产报销", "fields": ["报销人", "部门", "费用日期", "金额", "说明", "资产类型", "授权期限", "使用范围"], "version": 1, "is_active": True},
    {"id": str(uuid.uuid4())[:64], "form_code": "FM-EXP-020", "form_name": "税费缴纳申请单(B4)", "form_type": "expense", "category": "expense", "description": "税费缴纳申请", "fields": ["报销人", "部门", "费用日期", "金额", "说明", "税种", "税期", "应纳税额"], "version": 1, "is_active": True},
    {"id": str(uuid.uuid4())[:64], "form_code": "FM-ALR-001", "form_name": "预警响应表", "form_type": "alert", "category": "alert", "description": "预警响应处理", "fields": ["预警ID", "响应措施", "预计完成时间"], "version": 1, "is_active": True},
    {"id": str(uuid.uuid4())[:64], "form_code": "FM-ALR-002", "form_name": "预警闭环确认表", "form_type": "alert", "category": "alert", "description": "预警闭环确认", "fields": ["预警ID", "闭环类型", "确认人", "确认意见"], "version": 1, "is_active": True},
    {"id": str(uuid.uuid4())[:64], "form_code": "FM-ALR-003", "form_name": "预警升级申请表", "form_type": "alert", "category": "alert", "description": "预警升级申请", "fields": ["预警ID", "升级原因", "建议措施"], "version": 1, "is_active": True},
    {"id": str(uuid.uuid4())[:64], "form_code": "FM-ALR-004", "form_name": "预警汇总报告", "form_type": "alert", "category": "alert", "description": "预警汇总统计报告", "fields": ["期间", "预警统计", "未闭环清单"], "version": 1, "is_active": True},
    {"id": str(uuid.uuid4())[:64], "form_code": "FM-ALR-005", "form_name": "整改方案表", "form_type": "alert", "category": "alert", "description": "预警整改方案", "fields": ["预警ID", "整改措施", "责任人", "完成期限"], "version": 1, "is_active": True},
    {"id": str(uuid.uuid4())[:64], "form_code": "FM-ANA-001", "form_name": "执行率分析表", "form_type": "analysis", "category": "analysis", "description": "预算执行率分析", "fields": [], "version": 1, "is_active": True},
    {"id": str(uuid.uuid4())[:64], "form_code": "FM-ANA-002", "form_name": "3GAP分析表", "form_type": "analysis", "category": "analysis", "description": "3GAP差距分析", "fields": [], "version": 1, "is_active": True},
    {"id": str(uuid.uuid4())[:64], "form_code": "FM-ANA-003", "form_name": "3List分类表", "form_type": "analysis", "category": "analysis", "description": "3List行动清单分类", "fields": [], "version": 1, "is_active": True},
    {"id": str(uuid.uuid4())[:64], "form_code": "FM-ANA-004", "form_name": "象限合规检查表", "form_type": "analysis", "category": "analysis", "description": "象限合规性检查", "fields": [], "version": 1, "is_active": True},
    {"id": str(uuid.uuid4())[:64], "form_code": "FM-ANA-005", "form_name": "经营分析会材料", "form_type": "analysis", "category": "analysis", "description": "经营分析会议材料", "fields": [], "version": 1, "is_active": True},
    {"id": str(uuid.uuid4())[:64], "form_code": "FM-PDCA-001", "form_name": "月度复盘表", "form_type": "pdca", "category": "pdca", "description": "月度PDCA复盘", "fields": [], "version": 1, "is_active": True},
    {"id": str(uuid.uuid4())[:64], "form_code": "FM-PDCA-002", "form_name": "季度复盘表", "form_type": "pdca", "category": "pdca", "description": "季度PDCA复盘", "fields": [], "version": 1, "is_active": True},
    {"id": str(uuid.uuid4())[:64], "form_code": "FM-PDCA-003", "form_name": "年度复盘表", "form_type": "pdca", "category": "pdca", "description": "年度PDCA复盘", "fields": [], "version": 1, "is_active": True},
    {"id": str(uuid.uuid4())[:64], "form_code": "FM-PDCA-004", "form_name": "改进行动跟踪表", "form_type": "pdca", "category": "pdca", "description": "改进行动项跟踪", "fields": [], "version": 1, "is_active": True},
    {"id": str(uuid.uuid4())[:64], "form_code": "FM-PDCA-005", "form_name": "滚动预测表", "form_type": "pdca", "category": "pdca", "description": "滚动预测更新", "fields": [], "version": 1, "is_active": True},
    {"id": str(uuid.uuid4())[:64], "form_code": "FM-PDCA-006", "form_name": "象限调拨申请表", "form_type": "pdca", "category": "pdca", "description": "跨象限预算调拨申请", "fields": [], "version": 1, "is_active": True},
    {"id": str(uuid.uuid4())[:64], "form_code": "FM-RPT-001", "form_name": "月度快报", "form_type": "report", "category": "report", "description": "月度执行快报", "fields": [], "version": 1, "is_active": True},
    {"id": str(uuid.uuid4())[:64], "form_code": "FM-RPT-002", "form_name": "季度汇报", "form_type": "report", "category": "report", "description": "季度经营汇报", "fields": [], "version": 1, "is_active": True},
    {"id": str(uuid.uuid4())[:64], "form_code": "FM-RPT-003", "form_name": "年度复盘报告", "form_type": "report", "category": "report", "description": "年度复盘报告", "fields": [], "version": 1, "is_active": True},
    {"id": str(uuid.uuid4())[:64], "form_code": "FM-RPT-004", "form_name": "战略意图执行追踪表", "form_type": "report", "category": "report", "description": "战略意图执行追踪", "fields": [], "version": 1, "is_active": True},
    {"id": str(uuid.uuid4())[:64], "form_code": "FM-RPT-005", "form_name": "经营分析会纪要", "form_type": "report", "category": "report", "description": "经营分析会议纪要", "fields": [], "version": 1, "is_active": True},
    {"id": str(uuid.uuid4())[:64], "form_code": "FM-LOOP-001", "form_name": "年度执行数据库", "form_type": "cycle", "category": "cycle", "description": "年度执行数据归集", "fields": [], "version": 1, "is_active": True},
    {"id": str(uuid.uuid4())[:64], "form_code": "FM-LOOP-002", "form_name": "未关闭预警清单", "form_type": "cycle", "category": "cycle", "description": "未关闭预警清单", "fields": [], "version": 1, "is_active": True},
    {"id": str(uuid.uuid4())[:64], "form_code": "FM-LOOP-003", "form_name": "新循环启动申请表", "form_type": "cycle", "category": "cycle", "description": "新年度循环启动申请", "fields": [], "version": 1, "is_active": True},
    {"id": str(uuid.uuid4())[:64], "form_code": "FM-LOOP-004", "form_name": "复盘结论落地跟踪表", "form_type": "cycle", "category": "cycle", "description": "复盘结论落地跟踪", "fields": [], "version": 1, "is_active": True},
    {"id": str(uuid.uuid4())[:64], "form_code": "FM-LOOP-005", "form_name": "战略调整依据表", "form_type": "cycle", "category": "cycle", "description": "战略调整依据记录", "fields": [], "version": 1, "is_active": True},
]


async def seed_forms(db: AsyncSession) -> None:
    logger.info("Seeding form templates...")
    for data in FORM_TEMPLATES:
        from sqlalchemy import select
        stmt = select(FormTemplate).where(FormTemplate.form_code == data["form_code"])
        result = await db.execute(stmt)
        existing = result.scalar_one_or_none()
        if existing is None:
            db.add(FormTemplate(**data))
    await db.flush()
    logger.info("Form templates seed completed.")
