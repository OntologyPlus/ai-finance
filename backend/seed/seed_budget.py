from datetime import datetime
from decimal import Decimal

from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from models.budget import BudgetSubjectL1, BudgetSubjectL2, BudgetSubjectL3, BudgetItem, B2AConversion, ControlMode


L1_SUBJECTS = [
    {"l1_code": "B1", "l1_name": "资本支出", "management_mode": "项目化管理", "alert_rule_type": "通用+专项", "has_l2": True, "description": "固定资产、无形资产、工程建设等资本性支出"},
    {"l1_code": "B2", "l1_name": "研发支出", "management_mode": "项目化管理", "alert_rule_type": "通用+专项", "has_l2": False, "description": "研发项目投入、临床试验、合作研发等费用"},
    {"l1_code": "B3", "l1_name": "维持性支出", "management_mode": "通用管控", "alert_rule_type": "通用+专项", "has_l2": False, "description": "日常运营维持所需的差旅、租金、维修等费用"},
    {"l1_code": "B4", "l1_name": "税务支出", "management_mode": "合规导向", "alert_rule_type": "通用+专项", "has_l2": False, "description": "增值税、企业所得税等各类税费支出"},
    {"l1_code": "B5", "l1_name": "市场推广支出", "management_mode": "项目化管理", "alert_rule_type": "通用+专项", "has_l2": True, "description": "市场推广、学术活动、品牌建设等费用"},
    {"l1_code": "B6", "l1_name": "人力成本支出", "management_mode": "通用管控", "alert_rule_type": "通用+专项", "has_l2": False, "description": "员工薪酬、社保公积金、福利等人力成本"},
    {"l1_code": "B7", "l1_name": "货物支出", "management_mode": "通用管控", "alert_rule_type": "通用+专项", "has_l2": True, "description": "原材料、成品采购及仓储物流等费用"},
    {"l1_code": "B8", "l1_name": "股权投资支出", "management_mode": "项目化管理", "alert_rule_type": "通用+专项", "has_l2": False, "description": "股权投资、基金投资等投资性支出"},
    {"l1_code": "B9", "l1_name": "财务费用", "management_mode": "通用管控", "alert_rule_type": "通用+专项", "has_l2": False, "description": "银行手续费、利息支出等财务相关费用"},
]

L2_SUBJECTS = [
    {"l2_code": "B1-1", "l2_name": "无形资产支出", "l1_code": "B1", "special_rules": "无形资产须资产评估", "roi_threshold": None},
    {"l2_code": "B1-2", "l2_name": "工程支出", "l1_code": "B1", "special_rules": "工程支出须立项审批", "roi_threshold": None},
    {"l2_code": "B1-3", "l2_name": "固定资产支出", "l1_code": "B1", "special_rules": "固定资产采购须技术评审", "roi_threshold": None},
    {"l2_code": "B5-1", "l2_name": "销售驱动类推广", "l1_code": "B5", "special_rules": "按销售目标归集", "roi_threshold": "ROI≥1.5"},
    {"l2_code": "B5-2", "l2_name": "市场驱动类推广", "l1_code": "B5", "special_rules": "按市场活动归集", "roi_threshold": "ROI≥1.2"},
    {"l2_code": "B5-3", "l2_name": "医学驱动类推广", "l1_code": "B5", "special_rules": "按医学项目归集", "roi_threshold": "ROI≥1.3"},
    {"l2_code": "B5-4", "l2_name": "患者驱动类推广", "l1_code": "B5", "special_rules": "须合规审批", "roi_threshold": None},
    {"l2_code": "B5-5", "l2_name": "政策驱动类推广", "l1_code": "B5", "special_rules": "须政策合规审核", "roi_threshold": None},
    {"l2_code": "B5-6", "l2_name": "开发驱动类推广", "l1_code": "B5", "special_rules": "须商业论证", "roi_threshold": "ROI≥2.0"},
    {"l2_code": "B7-1", "l2_name": "成品采购", "l1_code": "B7", "special_rules": "采购须供应商评审", "roi_threshold": None},
    {"l2_code": "B7-2", "l2_name": "委托加工", "l1_code": "B7", "special_rules": "委托加工须质量协议", "roi_threshold": None},
    {"l2_code": "B7-3", "l2_name": "自主生产", "l1_code": "B7", "special_rules": None, "roi_threshold": None},
]

L3_SUBJECTS = [
    {"l3_code": "B1-1-01", "l3_name": "土地使用权", "l2_code": "B1-1", "l1_code": "B1", "control_tag": "强管控", "variety_group": "VG01", "is_project_managed": True, "alert_rules": '["SR-001","SR-002","SR-011"]'},
    {"l3_code": "B1-1-02", "l3_name": "专利权", "l2_code": "B1-1", "l1_code": "B1", "control_tag": "强管控", "variety_group": "VG01", "is_project_managed": True, "alert_rules": '["SR-001","SR-002","SR-011"]'},
    {"l3_code": "B1-1-03", "l3_name": "软件许可", "l2_code": "B1-1", "l1_code": "B1", "control_tag": "强管控", "variety_group": "VG01", "is_project_managed": True, "alert_rules": '["SR-001","SR-011"]'},
    {"l3_code": "B1-2-01", "l3_name": "土建工程", "l2_code": "B1-2", "l1_code": "B1", "control_tag": "强管控", "variety_group": "VG01", "is_project_managed": True, "alert_rules": '["SR-001","SR-002","SR-011"]'},
    {"l3_code": "B1-2-02", "l3_name": "安装工程", "l2_code": "B1-2", "l1_code": "B1", "control_tag": "强管控", "variety_group": "VG01", "is_project_managed": True, "alert_rules": '["SR-001","SR-002","SR-011"]'},
    {"l3_code": "B1-2-03", "l3_name": "装修工程", "l2_code": "B1-2", "l1_code": "B1", "control_tag": "强管控", "variety_group": "VG01", "is_project_managed": True, "alert_rules": '["SR-001","SR-011"]'},
    {"l3_code": "B1-2-04", "l3_name": "工程监理", "l2_code": "B1-2", "l1_code": "B1", "control_tag": "组合管控", "variety_group": "VG01", "is_project_managed": True, "alert_rules": '["SR-001","SR-011"]'},
    {"l3_code": "B1-2-05", "l3_name": "工程设计", "l2_code": "B1-2", "l1_code": "B1", "control_tag": "组合管控", "variety_group": "VG01", "is_project_managed": True, "alert_rules": '["SR-001","SR-011"]'},
    {"l3_code": "B1-3-01", "l3_name": "仓储设备", "l2_code": "B1-3", "l1_code": "B1", "control_tag": "强管控", "variety_group": "VG01", "is_project_managed": True, "alert_rules": '["SR-001","SR-002","SR-011"]'},
    {"l3_code": "B1-3-02", "l3_name": "办公设备", "l2_code": "B1-3", "l1_code": "B1", "control_tag": "强管控", "variety_group": "VG01", "is_project_managed": True, "alert_rules": '["SR-001","SR-011"]'},
    {"l3_code": "B1-3-03", "l3_name": "生产设备", "l2_code": "B1-3", "l1_code": "B1", "control_tag": "强管控", "variety_group": "VG01", "is_project_managed": True, "alert_rules": '["SR-001","SR-002","SR-011"]'},
    {"l3_code": "B1-3-04", "l3_name": "运输设备", "l2_code": "B1-3", "l1_code": "B1", "control_tag": "强管控", "variety_group": "VG01", "is_project_managed": True, "alert_rules": '["SR-001","SR-011"]'},
    {"l3_code": "B1-3-05", "l3_name": "实验设备", "l2_code": "B1-3", "l1_code": "B1", "control_tag": "强管控", "variety_group": "VG01", "is_project_managed": True, "alert_rules": '["SR-001","SR-002","SR-011"]'},
    {"l3_code": "B1-3-06", "l3_name": "IT设备", "l2_code": "B1-3", "l1_code": "B1", "control_tag": "强管控", "variety_group": "VG01", "is_project_managed": True, "alert_rules": '["SR-001","SR-011"]'},
    {"l3_code": "B1-3-07", "l3_name": "财产保险", "l2_code": "B1-3", "l1_code": "B1", "control_tag": "中心弱管控", "variety_group": "VG01", "is_project_managed": False, "alert_rules": '["SR-001"]'},
    {"l3_code": "B2-00-01", "l3_name": "产品注册费", "l2_code": None, "l1_code": "B2", "control_tag": "强管控", "variety_group": "VG02", "is_project_managed": True, "alert_rules": '["SR-001","SR-002","SR-011"]'},
    {"l3_code": "B2-00-02", "l3_name": "CDMO", "l2_code": None, "l1_code": "B2", "control_tag": "强管控", "variety_group": "VG02", "is_project_managed": True, "alert_rules": '["SR-001","SR-002","SR-008","SR-011"]'},
    {"l3_code": "B2-00-03", "l3_name": "CRO", "l2_code": None, "l1_code": "B2", "control_tag": "强管控", "variety_group": "VG02", "is_project_managed": True, "alert_rules": '["SR-001","SR-002","SR-008","SR-011"]'},
    {"l3_code": "B2-00-04", "l3_name": "CTA补贴", "l2_code": None, "l1_code": "B2", "control_tag": "组合管控", "variety_group": "VG02", "is_project_managed": True, "alert_rules": '["SR-001","SR-011"]'},
    {"l3_code": "B2-00-05", "l3_name": "SMO", "l2_code": None, "l1_code": "B2", "control_tag": "强管控", "variety_group": "VG02", "is_project_managed": True, "alert_rules": '["SR-001","SR-002","SR-011"]'},
    {"l3_code": "B2-00-06", "l3_name": "专家费", "l2_code": None, "l1_code": "B2", "control_tag": "组合管控", "variety_group": "VG02", "is_project_managed": True, "alert_rules": '["SR-001","SR-008","SR-011"]'},
    {"l3_code": "B2-00-07", "l3_name": "会议费", "l2_code": None, "l1_code": "B2", "control_tag": "中心弱管控", "variety_group": "VG02", "is_project_managed": True, "alert_rules": '["SR-001","SR-011"]'},
    {"l3_code": "B2-00-08", "l3_name": "招募费", "l2_code": None, "l1_code": "B2", "control_tag": "组合管控", "variety_group": "VG02", "is_project_managed": True, "alert_rules": '["SR-001","SR-011"]'},
    {"l3_code": "B2-00-09", "l3_name": "数据统计", "l2_code": None, "l1_code": "B2", "control_tag": "中心弱管控", "variety_group": "VG02", "is_project_managed": True, "alert_rules": '["SR-001","SR-011"]'},
    {"l3_code": "B2-00-10", "l3_name": "物料费", "l2_code": None, "l1_code": "B2", "control_tag": "中心弱管控", "variety_group": "VG02", "is_project_managed": True, "alert_rules": '["SR-001"]'},
    {"l3_code": "B2-00-11", "l3_name": "检测分析", "l2_code": None, "l1_code": "B2", "control_tag": "组合管控", "variety_group": "VG02", "is_project_managed": True, "alert_rules": '["SR-001","SR-011"]'},
    {"l3_code": "B2-00-12", "l3_name": "研究中心", "l2_code": None, "l1_code": "B2", "control_tag": "强管控", "variety_group": "VG02", "is_project_managed": True, "alert_rules": '["SR-001","SR-002","SR-011"]'},
    {"l3_code": "B2-00-13", "l3_name": "合作研发", "l2_code": None, "l1_code": "B2", "control_tag": "强管控", "variety_group": "VG02", "is_project_managed": True, "alert_rules": '["SR-001","SR-002","SR-008","SR-011"]'},
    {"l3_code": "B2-00-14", "l3_name": "其他研发", "l2_code": None, "l1_code": "B2", "control_tag": "不管控", "variety_group": "VG02", "is_project_managed": True, "alert_rules": '["SR-001"]'},
    {"l3_code": "B3-00-01", "l3_name": "差旅费", "l2_code": None, "l1_code": "B3", "control_tag": "中心弱管控", "variety_group": "VG03", "is_project_managed": False, "alert_rules": '["SR-001","SR-002"]'},
    {"l3_code": "B3-00-02", "l3_name": "市内交通", "l2_code": None, "l1_code": "B3", "control_tag": "中心弱管控", "variety_group": "VG03", "is_project_managed": False, "alert_rules": '["SR-001"]'},
    {"l3_code": "B3-00-03", "l3_name": "废污处理", "l2_code": None, "l1_code": "B3", "control_tag": "组合管控", "variety_group": "VG03", "is_project_managed": False, "alert_rules": '["SR-001","SR-002"]'},
    {"l3_code": "B3-00-04", "l3_name": "汽车费", "l2_code": None, "l1_code": "B3", "control_tag": "中心弱管控", "variety_group": "VG03", "is_project_managed": False, "alert_rules": '["SR-001"]'},
    {"l3_code": "B3-00-05", "l3_name": "特殊返利", "l2_code": None, "l1_code": "B3", "control_tag": "强管控", "variety_group": "VG03", "is_project_managed": False, "alert_rules": '["SR-001","SR-002","SR-008"]'},
    {"l3_code": "B3-00-06", "l3_name": "特许权使用费", "l2_code": None, "l1_code": "B3", "control_tag": "强管控", "variety_group": "VG03", "is_project_managed": False, "alert_rules": '["SR-001","SR-002"]'},
    {"l3_code": "B3-00-07", "l3_name": "租金水电", "l2_code": None, "l1_code": "B3", "control_tag": "中心弱管控", "variety_group": "VG03", "is_project_managed": False, "alert_rules": '["SR-001"]'},
    {"l3_code": "B3-00-08", "l3_name": "税金附加", "l2_code": None, "l1_code": "B3", "control_tag": "不管控", "variety_group": "VG03", "is_project_managed": False, "alert_rules": '["SR-001"]'},
    {"l3_code": "B3-00-09", "l3_name": "装修维修", "l2_code": None, "l1_code": "B3", "control_tag": "组合管控", "variety_group": "VG03", "is_project_managed": False, "alert_rules": '["SR-001","SR-002"]'},
    {"l3_code": "B3-00-10", "l3_name": "行政代垫", "l2_code": None, "l1_code": "B3", "control_tag": "中心弱管控", "variety_group": "VG03", "is_project_managed": False, "alert_rules": '["SR-001"]'},
    {"l3_code": "B3-00-11", "l3_name": "赔偿违约", "l2_code": None, "l1_code": "B3", "control_tag": "强管控", "variety_group": "VG03", "is_project_managed": False, "alert_rules": '["SR-001","SR-002","SR-008"]'},
    {"l3_code": "B3-00-12", "l3_name": "招待费", "l2_code": None, "l1_code": "B3", "control_tag": "中心弱管控", "variety_group": "VG03", "is_project_managed": False, "alert_rules": '["SR-001"]'},
    {"l3_code": "B3-00-13", "l3_name": "咨询及软件服务", "l2_code": None, "l1_code": "B3", "control_tag": "中心弱管控", "variety_group": "VG03", "is_project_managed": False, "alert_rules": '["SR-001","SR-011"]'},
    {"l3_code": "B4-00-01", "l3_name": "增值税", "l2_code": None, "l1_code": "B4", "control_tag": "不管控", "variety_group": "VG04", "is_project_managed": False, "alert_rules": '["SR-001"]'},
    {"l3_code": "B4-00-02", "l3_name": "企业所得税", "l2_code": None, "l1_code": "B4", "control_tag": "不管控", "variety_group": "VG04", "is_project_managed": False, "alert_rules": '["SR-001"]'},
    {"l3_code": "B4-00-03", "l3_name": "个人所得税", "l2_code": None, "l1_code": "B4", "control_tag": "不管控", "variety_group": "VG04", "is_project_managed": False, "alert_rules": '["SR-001"]'},
    {"l3_code": "B4-00-04", "l3_name": "印花税", "l2_code": None, "l1_code": "B4", "control_tag": "不管控", "variety_group": "VG04", "is_project_managed": False, "alert_rules": '["SR-001"]'},
    {"l3_code": "B4-00-05", "l3_name": "其他税费", "l2_code": None, "l1_code": "B4", "control_tag": "不管控", "variety_group": "VG04", "is_project_managed": False, "alert_rules": '["SR-001"]'},
    {"l3_code": "B5-1-01", "l3_name": "TP商服务费", "l2_code": "B5-1", "l1_code": "B5", "control_tag": "强管控", "variety_group": "VG05", "is_project_managed": True, "alert_rules": '["SR-001","SR-002","SR-011"]'},
    {"l3_code": "B5-1-02", "l3_name": "平台服务费", "l2_code": "B5-1", "l1_code": "B5", "control_tag": "强管控", "variety_group": "VG05", "is_project_managed": True, "alert_rules": '["SR-001","SR-002","SR-011"]'},
    {"l3_code": "B5-1-03", "l3_name": "品牌建设", "l2_code": "B5-1", "l1_code": "B5", "control_tag": "组合管控", "variety_group": "VG05", "is_project_managed": True, "alert_rules": '["SR-001","SR-011"]'},
    {"l3_code": "B5-2-01", "l3_name": "企业传播", "l2_code": "B5-2", "l1_code": "B5", "control_tag": "强管控", "variety_group": "VG05", "is_project_managed": True, "alert_rules": '["SR-001","SR-002","SR-011"]'},
    {"l3_code": "B5-2-02", "l3_name": "数字营销", "l2_code": "B5-2", "l1_code": "B5", "control_tag": "组合管控", "variety_group": "VG05", "is_project_managed": True, "alert_rules": '["SR-001","SR-011"]'},
    {"l3_code": "B5-2-03", "l3_name": "市场调研", "l2_code": "B5-2", "l1_code": "B5", "control_tag": "组合管控", "variety_group": "VG05", "is_project_managed": True, "alert_rules": '["SR-001","SR-011"]'},
    {"l3_code": "B5-3-01", "l3_name": "学术推广", "l2_code": "B5-3", "l1_code": "B5", "control_tag": "强管控", "variety_group": "VG05", "is_project_managed": True, "alert_rules": '["SR-001","SR-002","SR-011"]'},
    {"l3_code": "B5-3-02", "l3_name": "医学会议", "l2_code": "B5-3", "l1_code": "B5", "control_tag": "中心弱管控", "variety_group": "VG05", "is_project_managed": True, "alert_rules": '["SR-001","SR-011"]'},
    {"l3_code": "B5-3-03", "l3_name": "渠道推广", "l2_code": "B5-3", "l1_code": "B5", "control_tag": "组合管控", "variety_group": "VG05", "is_project_managed": True, "alert_rules": '["SR-001","SR-011"]'},
    {"l3_code": "B5-4-01", "l3_name": "患者援助", "l2_code": "B5-4", "l1_code": "B5", "control_tag": "强管控", "variety_group": "VG05", "is_project_managed": True, "alert_rules": '["SR-001","SR-002","SR-011"]'},
    {"l3_code": "B5-4-02", "l3_name": "患者教育", "l2_code": "B5-4", "l1_code": "B5", "control_tag": "组合管控", "variety_group": "VG05", "is_project_managed": True, "alert_rules": '["SR-001","SR-011"]'},
    {"l3_code": "B5-5-01", "l3_name": "KOL维护", "l2_code": "B5-5", "l1_code": "B5", "control_tag": "强管控", "variety_group": "VG05", "is_project_managed": True, "alert_rules": '["SR-001","SR-002","SR-008","SR-011"]'},
    {"l3_code": "B5-5-02", "l3_name": "招标挂网", "l2_code": "B5-5", "l1_code": "B5", "control_tag": "组合管控", "variety_group": "VG05", "is_project_managed": True, "alert_rules": '["SR-001","SR-011"]'},
    {"l3_code": "B5-5-03", "l3_name": "政策研究", "l2_code": "B5-5", "l1_code": "B5", "control_tag": "中心弱管控", "variety_group": "VG05", "is_project_managed": True, "alert_rules": '["SR-001"]'},
    {"l3_code": "B5-6-01", "l3_name": "新市场开拓", "l2_code": "B5-6", "l1_code": "B5", "control_tag": "强管控", "variety_group": "VG05", "is_project_managed": True, "alert_rules": '["SR-001","SR-002","SR-011"]'},
    {"l3_code": "B5-6-02", "l3_name": "开发驱动", "l2_code": "B5-6", "l1_code": "B5", "control_tag": "强管控", "variety_group": "VG05", "is_project_managed": True, "alert_rules": '["SR-001","SR-002","SR-011"]'},
    {"l3_code": "B6-00-01", "l3_name": "基本工资", "l2_code": None, "l1_code": "B6", "control_tag": "不管控", "variety_group": "VG06", "is_project_managed": False, "alert_rules": '["SR-001"]'},
    {"l3_code": "B6-00-02", "l3_name": "绩效奖金", "l2_code": None, "l1_code": "B6", "control_tag": "组合管控", "variety_group": "VG06", "is_project_managed": False, "alert_rules": '["SR-001","SR-002"]'},
    {"l3_code": "B6-00-03", "l3_name": "社保", "l2_code": None, "l1_code": "B6", "control_tag": "不管控", "variety_group": "VG06", "is_project_managed": False, "alert_rules": '["SR-001"]'},
    {"l3_code": "B6-00-04", "l3_name": "公积金", "l2_code": None, "l1_code": "B6", "control_tag": "不管控", "variety_group": "VG06", "is_project_managed": False, "alert_rules": '["SR-001"]'},
    {"l3_code": "B6-00-05", "l3_name": "福利费", "l2_code": None, "l1_code": "B6", "control_tag": "中心弱管控", "variety_group": "VG06", "is_project_managed": False, "alert_rules": '["SR-001"]'},
    {"l3_code": "B6-00-06", "l3_name": "培训费", "l2_code": None, "l1_code": "B6", "control_tag": "组合管控", "variety_group": "VG06", "is_project_managed": False, "alert_rules": '["SR-001","SR-002"]'},
    {"l3_code": "B6-00-07", "l3_name": "招聘费", "l2_code": None, "l1_code": "B6", "control_tag": "中心弱管控", "variety_group": "VG06", "is_project_managed": False, "alert_rules": '["SR-001"]'},
    {"l3_code": "B6-00-08", "l3_name": "劳务费", "l2_code": None, "l1_code": "B6", "control_tag": "强管控", "variety_group": "VG06", "is_project_managed": False, "alert_rules": '["SR-001","SR-002","SR-008"]'},
    {"l3_code": "B6-00-09", "l3_name": "离职补偿", "l2_code": None, "l1_code": "B6", "control_tag": "组合管控", "variety_group": "VG06", "is_project_managed": False, "alert_rules": '["SR-001","SR-002"]'},
    {"l3_code": "B6-00-10", "l3_name": "其他人力", "l2_code": None, "l1_code": "B6", "control_tag": "不管控", "variety_group": "VG06", "is_project_managed": False, "alert_rules": '["SR-001"]'},
    {"l3_code": "B7-1-01", "l3_name": "材料采购", "l2_code": "B7-1", "l1_code": "B7", "control_tag": "强管控", "variety_group": "VG07", "is_project_managed": False, "alert_rules": '["SR-001","SR-002"]'},
    {"l3_code": "B7-1-02", "l3_name": "成品采购", "l2_code": "B7-1", "l1_code": "B7", "control_tag": "强管控", "variety_group": "VG07", "is_project_managed": False, "alert_rules": '["SR-001","SR-002"]'},
    {"l3_code": "B7-1-03", "l3_name": "国内运杂", "l2_code": "B7-1", "l1_code": "B7", "control_tag": "中心弱管控", "variety_group": "VG07", "is_project_managed": False, "alert_rules": '["SR-001"]'},
    {"l3_code": "B7-1-04", "l3_name": "国际物流", "l2_code": "B7-1", "l1_code": "B7", "control_tag": "组合管控", "variety_group": "VG07", "is_project_managed": False, "alert_rules": '["SR-001","SR-002"]'},
    {"l3_code": "B7-1-05", "l3_name": "国内仓储", "l2_code": "B7-1", "l1_code": "B7", "control_tag": "中心弱管控", "variety_group": "VG07", "is_project_managed": False, "alert_rules": '["SR-001"]'},
    {"l3_code": "B7-2-01", "l3_name": "委托加工费", "l2_code": "B7-2", "l1_code": "B7", "control_tag": "强管控", "variety_group": "VG07", "is_project_managed": False, "alert_rules": '["SR-001","SR-002"]'},
    {"l3_code": "B7-2-02", "l3_name": "包装费", "l2_code": "B7-2", "l1_code": "B7", "control_tag": "中心弱管控", "variety_group": "VG07", "is_project_managed": False, "alert_rules": '["SR-001"]'},
    {"l3_code": "B7-2-03", "l3_name": "质检费", "l2_code": "B7-2", "l1_code": "B7", "control_tag": "组合管控", "variety_group": "VG07", "is_project_managed": False, "alert_rules": '["SR-001","SR-002"]'},
    {"l3_code": "B7-3-01", "l3_name": "供应商管理", "l2_code": "B7-3", "l1_code": "B7", "control_tag": "组合管控", "variety_group": "VG07", "is_project_managed": False, "alert_rules": '["SR-001","SR-002"]'},
    {"l3_code": "B7-3-02", "l3_name": "库存损耗", "l2_code": "B7-3", "l1_code": "B7", "control_tag": "中心弱管控", "variety_group": "VG07", "is_project_managed": False, "alert_rules": '["SR-001"]'},
    {"l3_code": "B7-3-03", "l3_name": "进口关税", "l2_code": "B7-3", "l1_code": "B7", "control_tag": "不管控", "variety_group": "VG07", "is_project_managed": False, "alert_rules": '["SR-001"]'},
    {"l3_code": "B7-3-04", "l3_name": "保税仓储", "l2_code": "B7-3", "l1_code": "B7", "control_tag": "组合管控", "variety_group": "VG07", "is_project_managed": False, "alert_rules": '["SR-001","SR-002"]'},
    {"l3_code": "B7-3-05", "l3_name": "其他货物", "l2_code": "B7-3", "l1_code": "B7", "control_tag": "不管控", "variety_group": "VG07", "is_project_managed": False, "alert_rules": '["SR-001"]'},
    {"l3_code": "B8-00-01", "l3_name": "股权投资", "l2_code": None, "l1_code": "B8", "control_tag": "强管控", "variety_group": "VG08", "is_project_managed": True, "alert_rules": '["SR-001","SR-002","SR-011"]'},
    {"l3_code": "B8-00-02", "l3_name": "基金投资", "l2_code": None, "l1_code": "B8", "control_tag": "强管控", "variety_group": "VG08", "is_project_managed": True, "alert_rules": '["SR-001","SR-002","SR-011"]'},
    {"l3_code": "B8-00-03", "l3_name": "投资管理费", "l2_code": None, "l1_code": "B8", "control_tag": "中心弱管控", "variety_group": "VG08", "is_project_managed": True, "alert_rules": '["SR-001"]'},
    {"l3_code": "B8-00-04", "l3_name": "投资收益", "l2_code": None, "l1_code": "B8", "control_tag": "组合管控", "variety_group": "VG08", "is_project_managed": True, "alert_rules": '["SR-001","SR-011"]'},
    {"l3_code": "B9-00-01", "l3_name": "银行手续费", "l2_code": None, "l1_code": "B9", "control_tag": "不管控", "variety_group": "VG09", "is_project_managed": False, "alert_rules": '["SR-001"]'},
    {"l3_code": "B9-00-02", "l3_name": "利息支出", "l2_code": None, "l1_code": "B9", "control_tag": "强管控", "variety_group": "VG09", "is_project_managed": False, "alert_rules": '["SR-001","SR-002"]'},
    {"l3_code": "B9-00-03", "l3_name": "汇兑损益", "l2_code": None, "l1_code": "B9", "control_tag": "组合管控", "variety_group": "VG09", "is_project_managed": False, "alert_rules": '["SR-001","SR-002"]'},
    {"l3_code": "B9-00-04", "l3_name": "其他财务费用", "l2_code": None, "l1_code": "B9", "control_tag": "中心弱管控", "variety_group": "VG09", "is_project_managed": False, "alert_rules": '["SR-001"]'},
]

BUDGET_ITEMS = [
    {"budget_id": "BG-2026-001", "budget_name": "津康中心-资本支出-土建工程", "budget_category": "A", "l1_code": "B1", "l2_code": "B1-2", "l3_code": "B1-2-01", "quadrant": "发展", "strategy_initiative_id": "SI-001", "annual_amount": Decimal("5000000.00"), "granted_amount": Decimal("5000000.00"), "frozen_amount": Decimal("5000000.00"), "used_amount": Decimal("2200000.00"), "available_amount": Decimal("2800000.00"), "grant_percentage": Decimal("100.00"), "status": "执行中", "center_id": "C001", "department_id": "D001"},
    {"budget_id": "BG-2026-002", "budget_name": "津康中心-研发支出-CRO", "budget_category": "A", "l1_code": "B2", "l2_code": None, "l3_code": "B2-00-03", "quadrant": "发展", "strategy_initiative_id": "SI-002", "annual_amount": Decimal("3500000.00"), "granted_amount": Decimal("3500000.00"), "frozen_amount": Decimal("3500000.00"), "used_amount": Decimal("1500000.00"), "available_amount": Decimal("2000000.00"), "grant_percentage": Decimal("100.00"), "status": "执行中", "center_id": "C001", "department_id": "D003", "project_id": "PRJ-001"},
    {"budget_id": "BG-2026-003", "budget_name": "津康中心-市场推广-学术推广", "budget_category": "B", "l1_code": "B5", "l2_code": "B5-3", "l3_code": "B5-3-01", "quadrant": "探索", "strategy_initiative_id": "SI-003", "annual_amount": Decimal("800000.00"), "granted_amount": Decimal("240000.00"), "frozen_amount": Decimal("0.00"), "used_amount": Decimal("180000.00"), "available_amount": Decimal("60000.00"), "grant_percentage": Decimal("30.00"), "status": "执行中", "center_id": "C001", "department_id": "D002", "project_id": "PRJ-002"},
    {"budget_id": "BG-2026-004", "budget_name": "华北中心-货物支出-成品采购", "budget_category": "A", "l1_code": "B7", "l2_code": "B7-1", "l3_code": "B7-1-02", "quadrant": "稳定", "strategy_initiative_id": None, "annual_amount": Decimal("2000000.00"), "granted_amount": Decimal("2000000.00"), "frozen_amount": Decimal("2000000.00"), "used_amount": Decimal("900000.00"), "available_amount": Decimal("1100000.00"), "grant_percentage": Decimal("100.00"), "status": "执行中", "center_id": "C002", "department_id": "D005"},
    {"budget_id": "BG-2026-005", "budget_name": "华北中心-税务支出-增值税", "budget_category": "A", "l1_code": "B4", "l2_code": None, "l3_code": "B4-00-01", "quadrant": "稳定", "strategy_initiative_id": None, "annual_amount": Decimal("2000000.00"), "granted_amount": Decimal("2000000.00"), "frozen_amount": Decimal("2000000.00"), "used_amount": Decimal("950000.00"), "available_amount": Decimal("1050000.00"), "grant_percentage": Decimal("100.00"), "status": "执行中", "center_id": "C002", "department_id": "D004"},
    {"budget_id": "BG-2026-006", "budget_name": "华北中心-股权投资-股权投资", "budget_category": "B", "l1_code": "B8", "l2_code": None, "l3_code": "B8-00-01", "quadrant": "探索", "strategy_initiative_id": "SI-004", "annual_amount": Decimal("600000.00"), "granted_amount": Decimal("180000.00"), "frozen_amount": Decimal("0.00"), "used_amount": Decimal("150000.00"), "available_amount": Decimal("30000.00"), "grant_percentage": Decimal("30.00"), "status": "执行中", "center_id": "C002", "department_id": "D006", "project_id": "PRJ-003"},
    {"budget_id": "BG-2026-007", "budget_name": "华东中心-研发支出-CDMO", "budget_category": "B", "l1_code": "B2", "l2_code": None, "l3_code": "B2-00-02", "quadrant": "探索", "strategy_initiative_id": "SI-005", "annual_amount": Decimal("1000000.00"), "granted_amount": Decimal("300000.00"), "frozen_amount": Decimal("0.00"), "used_amount": Decimal("250000.00"), "available_amount": Decimal("50000.00"), "grant_percentage": Decimal("30.00"), "status": "执行中", "center_id": "C003", "department_id": "D008", "project_id": "PRJ-004"},
    {"budget_id": "BG-2026-008", "budget_name": "华东中心-维持性支出-差旅费", "budget_category": "A", "l1_code": "B3", "l2_code": None, "l3_code": "B3-00-01", "quadrant": "稳定", "strategy_initiative_id": None, "annual_amount": Decimal("1200000.00"), "granted_amount": Decimal("1200000.00"), "frozen_amount": Decimal("1200000.00"), "used_amount": Decimal("580000.00"), "available_amount": Decimal("620000.00"), "grant_percentage": Decimal("100.00"), "status": "执行中", "center_id": "C003", "department_id": "D007"},
    {"budget_id": "BG-2026-009", "budget_name": "华东中心-人力成本-基本工资", "budget_category": "A", "l1_code": "B6", "l2_code": None, "l3_code": "B6-00-01", "quadrant": "稳定", "strategy_initiative_id": None, "annual_amount": Decimal("4500000.00"), "granted_amount": Decimal("4500000.00"), "frozen_amount": Decimal("4500000.00"), "used_amount": Decimal("2000000.00"), "available_amount": Decimal("2500000.00"), "grant_percentage": Decimal("100.00"), "status": "执行中", "center_id": "C003", "department_id": "D007"},
    {"budget_id": "BG-2026-010", "budget_name": "华南中心-财务费用-利息支出", "budget_category": "A", "l1_code": "B9", "l2_code": None, "l3_code": "B9-00-02", "quadrant": "收缩", "strategy_initiative_id": None, "annual_amount": Decimal("800000.00"), "granted_amount": Decimal("800000.00"), "frozen_amount": Decimal("800000.00"), "used_amount": Decimal("400000.00"), "available_amount": Decimal("400000.00"), "grant_percentage": Decimal("100.00"), "status": "执行中", "center_id": "C004", "department_id": "D010"},
    {"budget_id": "BG-2026-011", "budget_name": "华南中心-资本支出-生产设备", "budget_category": "A", "l1_code": "B1", "l2_code": "B1-3", "l3_code": "B1-3-03", "quadrant": "发展", "strategy_initiative_id": "SI-006", "annual_amount": Decimal("2800000.00"), "granted_amount": Decimal("2800000.00"), "frozen_amount": Decimal("2800000.00"), "used_amount": Decimal("1200000.00"), "available_amount": Decimal("1600000.00"), "grant_percentage": Decimal("100.00"), "status": "执行中", "center_id": "C004", "department_id": "D011"},
    {"budget_id": "BG-2026-012", "budget_name": "津康中心-人力成本-基本工资", "budget_category": "A", "l1_code": "B6", "l2_code": None, "l3_code": "B6-00-01", "quadrant": "稳定", "strategy_initiative_id": None, "annual_amount": Decimal("5000000.00"), "granted_amount": Decimal("5000000.00"), "frozen_amount": Decimal("5000000.00"), "used_amount": Decimal("2200000.00"), "available_amount": Decimal("2800000.00"), "grant_percentage": Decimal("100.00"), "status": "执行中", "center_id": "C001", "department_id": "D001"},
    {"budget_id": "BG-2026-013", "budget_name": "华北中心-市场推广-平台服务费", "budget_category": "B", "l1_code": "B5", "l2_code": "B5-1", "l3_code": "B5-1-02", "quadrant": "探索", "strategy_initiative_id": "SI-007", "annual_amount": Decimal("900000.00"), "granted_amount": Decimal("270000.00"), "frozen_amount": Decimal("0.00"), "used_amount": Decimal("200000.00"), "available_amount": Decimal("70000.00"), "grant_percentage": Decimal("30.00"), "status": "执行中", "center_id": "C002", "department_id": "D004", "project_id": "PRJ-005"},
    {"budget_id": "BG-2026-014", "budget_name": "华东中心-货物支出-委托加工", "budget_category": "B", "l1_code": "B7", "l2_code": "B7-2", "l3_code": "B7-2-01", "quadrant": "探索", "strategy_initiative_id": "SI-008", "annual_amount": Decimal("1500000.00"), "granted_amount": Decimal("450000.00"), "frozen_amount": Decimal("0.00"), "used_amount": Decimal("350000.00"), "available_amount": Decimal("100000.00"), "grant_percentage": Decimal("30.00"), "status": "执行中", "center_id": "C003", "department_id": "D008"},
    {"budget_id": "BG-2026-015", "budget_name": "华南中心-研发支出-合作研发", "budget_category": "B", "l1_code": "B2", "l2_code": None, "l3_code": "B2-00-14", "quadrant": "探索", "strategy_initiative_id": "SI-009", "annual_amount": Decimal("500000.00"), "granted_amount": Decimal("150000.00"), "frozen_amount": Decimal("0.00"), "used_amount": Decimal("120000.00"), "available_amount": Decimal("30000.00"), "grant_percentage": Decimal("30.00"), "status": "执行中", "center_id": "C004", "department_id": "D012", "project_id": "PRJ-006"},
    {"budget_id": "BG-2026-016", "budget_name": "津康中心-维持性支出-租金水电", "budget_category": "A", "l1_code": "B3", "l2_code": None, "l3_code": "B3-00-07", "quadrant": "收缩", "strategy_initiative_id": None, "annual_amount": Decimal("300000.00"), "granted_amount": Decimal("300000.00"), "frozen_amount": Decimal("300000.00"), "used_amount": Decimal("140000.00"), "available_amount": Decimal("160000.00"), "grant_percentage": Decimal("100.00"), "status": "执行中", "center_id": "C001", "department_id": "D002"},
    {"budget_id": "BG-2026-017", "budget_name": "华南中心-市场推广-新市场开拓", "budget_category": "A", "l1_code": "B5", "l2_code": "B5-6", "l3_code": "B5-6-01", "quadrant": "发展", "strategy_initiative_id": "SI-010", "annual_amount": Decimal("1800000.00"), "granted_amount": Decimal("1800000.00"), "frozen_amount": Decimal("1800000.00"), "used_amount": Decimal("800000.00"), "available_amount": Decimal("1000000.00"), "grant_percentage": Decimal("100.00"), "status": "执行中", "center_id": "C004", "department_id": "D011", "project_id": "PRJ-007"},
    {"budget_id": "BG-2026-018", "budget_name": "华北中心-资本支出-土地使用权", "budget_category": "A", "l1_code": "B1", "l2_code": "B1-1", "l3_code": "B1-1-01", "quadrant": "发展", "strategy_initiative_id": "SI-011", "annual_amount": Decimal("8000000.00"), "granted_amount": Decimal("8000000.00"), "frozen_amount": Decimal("8000000.00"), "used_amount": Decimal("3500000.00"), "available_amount": Decimal("4500000.00"), "grant_percentage": Decimal("100.00"), "status": "执行中", "center_id": "C002", "department_id": "D005"},
    {"budget_id": "BG-2026-019", "budget_name": "津康中心-市场推广-患者援助", "budget_category": "A", "l1_code": "B5", "l2_code": "B5-4", "l3_code": "B5-4-01", "quadrant": "发展", "strategy_initiative_id": "SI-012", "annual_amount": Decimal("1500000.00"), "granted_amount": Decimal("0.00"), "frozen_amount": Decimal("0.00"), "used_amount": Decimal("0.00"), "available_amount": Decimal("0.00"), "grant_percentage": Decimal("0.00"), "status": "编制中", "center_id": "C001", "department_id": "D002", "project_id": "PRJ-008"},
    {"budget_id": "BG-2026-020", "budget_name": "华东中心-人力成本-绩效奖金", "budget_category": "A", "l1_code": "B6", "l2_code": None, "l3_code": "B6-00-02", "quadrant": "稳定", "strategy_initiative_id": None, "annual_amount": Decimal("1200000.00"), "granted_amount": Decimal("1200000.00"), "frozen_amount": Decimal("1200000.00"), "used_amount": Decimal("500000.00"), "available_amount": Decimal("700000.00"), "grant_percentage": Decimal("100.00"), "status": "已授予", "center_id": "C003", "department_id": "D007"},
    {"budget_id": "BG-2026-021", "budget_name": "华南中心-维持性支出-差旅费", "budget_category": "A", "l1_code": "B3", "l2_code": None, "l3_code": "B3-00-01", "quadrant": "稳定", "strategy_initiative_id": None, "annual_amount": Decimal("600000.00"), "granted_amount": Decimal("600000.00"), "frozen_amount": Decimal("600000.00"), "used_amount": Decimal("600000.00"), "available_amount": Decimal("0.00"), "grant_percentage": Decimal("100.00"), "status": "已核销", "center_id": "C004", "department_id": "D010"},
    {"budget_id": "BG-2026-022", "budget_name": "华北中心-人力成本-社保", "budget_category": "A", "l1_code": "B6", "l2_code": None, "l3_code": "B6-00-03", "quadrant": "稳定", "strategy_initiative_id": None, "annual_amount": Decimal("3800000.00"), "granted_amount": Decimal("3800000.00"), "frozen_amount": Decimal("3800000.00"), "used_amount": Decimal("1700000.00"), "available_amount": Decimal("2100000.00"), "grant_percentage": Decimal("100.00"), "status": "执行中", "center_id": "C002", "department_id": "D004"},
]

B2A_CONVERSIONS = [
    {"conversion_id": "B2A-001", "budget_id": "BG-2026-003", "conversion_date": datetime(2026, 4, 15), "milestone_evidence": "Q1渠道拓展新增3个核心客户，签约金额超200万", "milestone_period": "Q1", "approver": "EMP-005", "approval_status": "已通过", "frozen_amount": Decimal("560000.00"), "report_to_committee": True},
    {"conversion_id": "B2A-002", "budget_id": "BG-2026-006", "conversion_date": datetime(2026, 5, 10), "milestone_evidence": "外包团队完成核心模块开发，通过技术评审", "milestone_period": "Q2", "approver": "EMP-010", "approval_status": "待审批", "frozen_amount": Decimal("420000.00"), "report_to_committee": False},
    {"conversion_id": "B2A-003", "budget_id": "BG-2026-007", "conversion_date": datetime(2026, 5, 20), "milestone_evidence": "数字营销ROI达到1.8，超过1.5阈值", "milestone_period": "Q2", "approver": None, "approval_status": "待审批", "frozen_amount": Decimal("700000.00"), "report_to_committee": False},
    {"conversion_id": "B2A-004", "budget_id": "BG-2026-014", "conversion_date": datetime(2026, 3, 28), "milestone_evidence": "华东新渠道拓展完成2个重点客户签约", "milestone_period": "Q1", "approver": "EMP-015", "approval_status": "已通过", "frozen_amount": Decimal("630000.00"), "report_to_committee": True},
    {"conversion_id": "B2A-005", "budget_id": "BG-2026-015", "conversion_date": datetime(2026, 5, 25), "milestone_evidence": "咨询项目中期评估达标", "milestone_period": "Q2", "approver": None, "approval_status": "已驳回", "frozen_amount": Decimal("0.00"), "report_to_committee": False},
]

CONTROL_MODES = [
    {"mode": "强管控", "code": "CTRL-01", "cross_dept_allowed": False, "cross_category_allowed": False, "cross_variety_group_allowed": False, "over_budget_action": "硬性拦截，禁止超预算支出", "description": "最严格管控模式，不可跨部门/类别/品种组，超预算硬拦截"},
    {"mode": "中心弱管控", "code": "CTRL-02", "cross_dept_allowed": True, "cross_category_allowed": False, "cross_variety_group_allowed": True, "over_budget_action": "中心内可调剂，须报备", "description": "中心内部可跨部门和品种组调剂，不可跨费用类别，超预算须报备"},
    {"mode": "组合管控", "code": "CTRL-03", "cross_dept_allowed": True, "cross_category_allowed": False, "cross_variety_group_allowed": True, "over_budget_action": "按组合规则执行，部分可调剂", "description": "组合管控模式，部分维度可调剂，按具体规则执行"},
    {"mode": "不管控", "code": "CTRL-04", "cross_dept_allowed": True, "cross_category_allowed": True, "cross_variety_group_allowed": True, "over_budget_action": "仅记录，不拦截", "description": "最宽松管控模式，全维度可调剂，超预算仅记录不拦截"},
]


async def seed_budget(db: AsyncSession) -> None:
    logger.info("Seeding budget subjects L1...")
    for data in L1_SUBJECTS:
        existing = await db.get(BudgetSubjectL1, data["l1_code"])
        if existing is None:
            db.add(BudgetSubjectL1(**data))
    await db.flush()

    logger.info("Seeding budget subjects L2...")
    for data in L2_SUBJECTS:
        existing = await db.get(BudgetSubjectL2, data["l2_code"])
        if existing is None:
            db.add(BudgetSubjectL2(**data))
    await db.flush()

    logger.info("Seeding budget subjects L3...")
    for data in L3_SUBJECTS:
        existing = await db.get(BudgetSubjectL3, data["l3_code"])
        if existing is None:
            db.add(BudgetSubjectL3(**data))
    await db.flush()

    logger.info("Seeding budget items...")
    for data in BUDGET_ITEMS:
        existing = await db.get(BudgetItem, data["budget_id"])
        if existing is None:
            db.add(BudgetItem(**data))
    await db.flush()

    logger.info("Seeding B2A conversions...")
    for data in B2A_CONVERSIONS:
        existing = await db.get(B2AConversion, data["conversion_id"])
        if existing is None:
            db.add(B2AConversion(**data))
    await db.flush()

    logger.info("Seeding control modes...")
    for data in CONTROL_MODES:
        existing = await db.get(ControlMode, data["mode"])
        if existing is None:
            db.add(ControlMode(**data))
    await db.flush()

    logger.info("Budget seed completed.")
