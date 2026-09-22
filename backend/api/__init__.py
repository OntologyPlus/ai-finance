from fastapi import APIRouter
from api.health import router as health_router
from api.budget import router as budget_router
from api.expense import router as expense_router
from api.approval import router as approval_router
from api.alert import router as alert_router
from api.analysis import router as analysis_router
from api.report import router as report_router
from api.pdca import router as pdca_router
from api.dashboard import router as dashboard_router
from api.ontology import router as ontology_router
from api.ontology_runtime import router as ontology_runtime_router
from api.eval import router as eval_router
from api.settings import router as settings_router
from api.stream import router as stream_router
from api.agents import router as agents_router
from api.strategic import router as strategic_router
from api.form import router as form_router
from api.contract import router as contract_router
from api.archive import router as archive_router
from api.pending_item import router as pending_item_router
from api.auth import router as auth_router
from api.cash_flow import router as cash_flow_router
from api.scenario import router as scenario_router
from api.impact_assessment import router as impact_assessment_router
from api.zero_based_budget import router as zero_based_budget_router
from api.cost_center import router as cost_center_router
from api.hcp_compliance import router as hcp_compliance_router
from api.pipeline import router as pipeline_router
from api.business_review import router as business_review_router
from api.insights import router as insights_router
from api.lineage import router as lineage_router
from api.decisions import router as decisions_router
from api.operational import router as operational_router

api_router = APIRouter()
api_router.include_router(health_router, prefix="/api", tags=["health"])
api_router.include_router(operational_router, prefix="/api", tags=["operational"])
api_router.include_router(budget_router, prefix="/api", tags=["budget"])
api_router.include_router(expense_router, prefix="/api", tags=["expense"])
api_router.include_router(approval_router, prefix="/api", tags=["approval"])
api_router.include_router(alert_router, prefix="/api", tags=["alert"])
api_router.include_router(analysis_router, prefix="/api", tags=["analysis"])
api_router.include_router(report_router, prefix="/api", tags=["report"])
api_router.include_router(pdca_router, prefix="/api", tags=["pdca"])
api_router.include_router(dashboard_router, prefix="/api", tags=["dashboard"])
api_router.include_router(ontology_router, prefix="/api", tags=["ontology"])
api_router.include_router(ontology_runtime_router, prefix="/api", tags=["ontology-runtime"])
api_router.include_router(eval_router, prefix="/api", tags=["eval"])
api_router.include_router(settings_router, prefix="/api", tags=["settings"])
api_router.include_router(stream_router, prefix="/api", tags=["stream"])
api_router.include_router(agents_router, prefix="/api", tags=["agents"])
api_router.include_router(strategic_router, prefix="/api", tags=["strategic"])
api_router.include_router(form_router, prefix="/api", tags=["form"])
api_router.include_router(contract_router, prefix="/api", tags=["contract"])
api_router.include_router(archive_router, prefix="/api", tags=["archive"])
api_router.include_router(pending_item_router, prefix="/api", tags=["pending-item"])
api_router.include_router(auth_router, prefix="/api", tags=["auth"])
api_router.include_router(cash_flow_router, prefix="/api", tags=["cash-flow"])
api_router.include_router(scenario_router, prefix="/api", tags=["scenario"])
api_router.include_router(impact_assessment_router, prefix="/api", tags=["impact-assessment"])
api_router.include_router(zero_based_budget_router, prefix="/api", tags=["zero-based-budget"])
api_router.include_router(cost_center_router, prefix="/api", tags=["cost-center"])
api_router.include_router(hcp_compliance_router, prefix="/api", tags=["hcp-compliance"])
api_router.include_router(pipeline_router, prefix="/api", tags=["pipeline"])
api_router.include_router(business_review_router, prefix="/api", tags=["business-review"])
api_router.include_router(insights_router, prefix="/api", tags=["insights"])
api_router.include_router(lineage_router, prefix="/api", tags=["lineage"])
api_router.include_router(decisions_router, prefix="/api", tags=["decisions"])
