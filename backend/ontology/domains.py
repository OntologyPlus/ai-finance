from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional, Set

from pydantic import BaseModel, Field

from ontology.objects import get_all_objects
from ontology.relations import get_all_relations
from ontology.behaviors import get_all_behaviors


class DomainId(str, Enum):
    BUDGET_CONTROL = "domain_budget_control"
    EXPENSE_EXECUTION = "domain_expense_execution"
    ALERT_MONITORING = "domain_alert_monitoring"
    REPORT_VALIDATION = "domain_report_validation"


class DomainDefinition(BaseModel):
    domain_id: DomainId
    name: str
    description: str
    core_objects: List[str] = Field(description="域核心对象ID列表")
    core_relations: List[str] = Field(description="域核心关系ID列表")
    core_behaviors: List[str] = Field(description="域核心行为ID列表")
    domain_admin: str = Field(description="域管理员角色")
    business_owner: str = Field(description="业务所有者角色")
    boundary_rules: List[str] = Field(default_factory=list, description="域边界规则")


class CrossDomainRequest(BaseModel):
    request_id: str
    source_domain: DomainId
    target_domain: DomainId
    relation_id: str
    description: str
    requester: str
    status: str = "pending"
    approver: Optional[str] = None
    approved_at: Optional[str] = None


_DOMAIN_DEFINITIONS: List[DomainDefinition] = [
    DomainDefinition(
        domain_id=DomainId.BUDGET_CONTROL,
        name="预算管控域",
        description="覆盖预算编制、授予、调整、B→A转换等全生命周期管控，确保预算配置与战略对齐",
        core_objects=[
            "obj_budget_item", "obj_budget_quadrant", "obj_budget_subject_l1",
            "obj_budget_subject_l2", "obj_budget_subject_l3", "obj_strategic_initiative",
        ],
        core_relations=["rel_benchmark", "rel_belong", "rel_freeze", "rel_release", "rel_b2a_convert", "rel_drive", "rel_adjudicate"],
        core_behaviors=[
            "fin.budget.a_class_freeze", "fin.budget.b_class_grant", "fin.budget.b2a_convert",
            "fin.budget.release", "fin.adjustment.transfer", "fin.pdca.yearly",
        ],
        domain_admin="财经中心预算管理部",
        business_owner="管委会",
        boundary_rules=[
            "预算调整影响费用执行域时须通知费用执行域管理员",
            "B→A转换完成后须同步更新费用执行域的管控规则",
        ],
    ),
    DomainDefinition(
        domain_id=DomainId.EXPENSE_EXECUTION,
        name="费用执行域",
        description="覆盖报销提交、审批路由、预算核销等费用执行全流程，确保支出合规",
        core_objects=["obj_expense_report", "obj_budget_subject_l3"],
        core_relations=["rel_mount", "rel_control", "rel_approval_org", "rel_approval_legal"],
        core_behaviors=[
            "fin.control.route", "fin.expense.submit",
            "fin.approval.org_line", "fin.approval.legal_line", "fin.budget.write_off",
        ],
        domain_admin="中心财经BP",
        business_owner="中心总经理",
        boundary_rules=[
            "费用核销完成后须通知预算管控域更新使用额度",
            "超预算支出触发预警时须通知预警监控域",
        ],
    ),
    DomainDefinition(
        domain_id=DomainId.ALERT_MONITORING,
        name="预警监控域",
        description="覆盖预警触发、响应、闭环、升级等预警全生命周期，确保风险可控",
        core_objects=["obj_alert_record"],
        core_relations=["rel_trigger", "rel_respond", "rel_confirm", "rel_escalate"],
        core_behaviors=[
            "fin.alert.create_monthly", "fin.alert.create_quarterly", "fin.alert.create_milestone",
            "fin.alert.escalate", "fin.alert.close",
        ],
        domain_admin="财经中心预算管理部",
        business_owner="管委会",
        boundary_rules=[
            "预警闭环后须通知报表验证域更新闭环率指标",
            "红色预警须通知预算管控域评估是否需要冻结额度",
        ],
    ),
    DomainDefinition(
        domain_id=DomainId.REPORT_VALIDATION,
        name="报表验证域",
        description="覆盖月度快报、季度汇报、年度复盘等报表出具和验证，确保数据定稿和锁定",
        core_objects=["obj_report_monthly", "obj_report_quarterly", "obj_report_yearly", "obj_tool_3gap_3list"],
        core_relations=[],
        core_behaviors=["fin.report.monthly", "fin.report.quarterly"],
        domain_admin="运营中心经营管理部",
        business_owner="管委会",
        boundary_rules=[
            "报表数据引用预算管控域数据时须确认数据版本已定稿",
            "报表引用预警数据时须确认预警闭环率已达标",
        ],
    ),
]

_CROSS_DOMAIN_APPROVAL_REQUIRED: Dict[str, Set[DomainId]] = {
    "rel_mount": {DomainId.BUDGET_CONTROL, DomainId.EXPENSE_EXECUTION},
    "rel_trigger": {DomainId.EXPENSE_EXECUTION, DomainId.ALERT_MONITORING},
    "rel_benchmark": {DomainId.BUDGET_CONTROL, DomainId.REPORT_VALIDATION},
}


class OntologyDomainManager:
    def __init__(self):
        self.domains = {d.domain_id: d for d in _DOMAIN_DEFINITIONS}
        self.cross_domain_rules = _CROSS_DOMAIN_APPROVAL_REQUIRED
        self._pending_requests: Dict[str, CrossDomainRequest] = {}

    def get_domain(self, domain_id: DomainId) -> Optional[DomainDefinition]:
        return self.domains.get(domain_id)

    def get_all_domains(self) -> Dict[DomainId, DomainDefinition]:
        return self.domains.copy()

    def get_domain_for_object(self, object_id: str) -> Optional[DomainDefinition]:
        for domain in self.domains.values():
            if object_id in domain.core_objects:
                return domain
        return None

    def get_domain_for_relation(self, relation_id: str) -> List[DomainDefinition]:
        result = []
        for domain in self.domains.values():
            if relation_id in domain.core_relations:
                result.append(domain)
        return result

    def is_cross_domain_relation(self, relation_id: str) -> bool:
        return relation_id in self.cross_domain_rules

    def get_cross_domain_info(self, relation_id: str) -> Optional[Set[DomainId]]:
        return self.cross_domain_rules.get(relation_id)

    def check_cohesion(self, domain_id: DomainId) -> Dict[str, Any]:
        domain = self.domains.get(domain_id)
        if domain is None:
            return {"domain_id": domain_id, "cohesive": False, "issues": ["域不存在"]}

        all_objects = get_all_objects()
        all_relations = get_all_relations()
        all_behaviors = get_all_behaviors()

        issues = []

        for obj_id in domain.core_objects:
            if obj_id not in all_objects:
                issues.append(f"核心对象 {obj_id} 不存在于Ontology中")

        for rel_id in domain.core_relations:
            if rel_id not in all_relations:
                issues.append(f"核心关系 {rel_id} 不存在于Ontology中")

        for beh_id in domain.core_behaviors:
            if beh_id not in all_behaviors:
                issues.append(f"核心行为 {beh_id} 不存在于Ontology中")

        for obj_id in domain.core_objects:
            obj = all_objects.get(obj_id)
            if obj and obj.participating_relations:
                for rel_name in obj.participating_relations:
                    rel_in_domain = False
                    for rel in all_relations.values():
                        if rel.name == rel_name and rel.relation_id in domain.core_relations:
                            rel_in_domain = True
                            break
                    if not rel_in_domain:
                        for rel in all_relations.values():
                            if rel.name == rel_name:
                                issues.append(f"对象 {obj_id} 参与关系 {rel_name} 但该关系不在域内，可能存在域边界问题")
                                break

        return {
            "domain_id": domain_id,
            "domain_name": domain.name,
            "cohesive": len(issues) == 0,
            "issues": issues,
            "object_count": len(domain.core_objects),
            "relation_count": len(domain.core_relations),
            "behavior_count": len(domain.core_behaviors),
        }

    def submit_cross_domain_request(
        self, source_domain: DomainId, target_domain: DomainId,
        relation_id: str, description: str, requester: str,
    ) -> CrossDomainRequest:
        request = CrossDomainRequest(
            request_id=f"CDR-{id(description):08x}",
            source_domain=source_domain,
            target_domain=target_domain,
            relation_id=relation_id,
            description=description,
            requester=requester,
        )
        self._pending_requests[request.request_id] = request
        return request

    def approve_cross_domain_request(self, request_id: str, approver: str) -> CrossDomainRequest:
        request = self._pending_requests.get(request_id)
        if request is None:
            raise ValueError(f"Cross-domain request {request_id} not found")
        if request.status != "pending":
            raise ValueError(f"Request {request_id} is already {request.status}")

        target_domain = self.domains.get(request.target_domain)
        if target_domain:
            authorized_approvers = {target_domain.domain_admin, target_domain.business_owner}
            if approver not in authorized_approvers:
                raise ValueError(f"{approver} 无权审批此跨域请求，需 {target_domain.domain_admin} 或 {target_domain.business_owner} 审批")

        from datetime import datetime
        request.status = "approved"
        request.approver = approver
        request.approved_at = datetime.now().isoformat()

        return request

    def get_all_cohesion_reports(self) -> List[Dict[str, Any]]:
        return [self.check_cohesion(did) for did in self.domains]
