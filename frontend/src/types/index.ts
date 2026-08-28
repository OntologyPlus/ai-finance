export type BudgetCategory = 'A' | 'B';
export type QuadrantType = '发展' | '收缩' | '稳定' | '探索';
export type ControlTag = 'strong' | 'weak' | 'combo' | 'none';
export type AlertLevel = 'red' | 'orange' | 'yellow' | 'blue';
export type ApprovalStatus = 'pending' | 'approved' | 'rejected' | 'cancelled';
export type ExpenseStatus = 'draft' | 'submitted' | 'org_approved' | 'legal_approved' | 'rejected' | 'written_off';
export type AlertStatus = 'active' | 'responded' | 'closed' | 'escalated';

export interface BudgetSubjectL1 {
  l1_code: string;
  l1_name: string;
  description?: string;
}

export interface BudgetSubjectL2 {
  l2_code: string;
  l1_code: string;
  l2_name: string;
  description?: string;
}

export interface BudgetSubjectL3 {
  l3_code: string;
  l2_code: string;
  l3_name: string;
  control_tag: ControlTag;
  description?: string;
}

export interface BudgetItem {
  budget_id: string;
  budget_category: BudgetCategory;
  l1_code: string;
  l2_code: string;
  l3_code: string;
  quadrant: QuadrantType;
  org_id: string;
  annual_amount: number;
  granted_amount: number;
  frozen_amount: number;
  used_amount: number;
  available_amount: number;
  year: number;
  description?: string;
  milestone_plan?: MilestonePlan[];
  created_at: string;
  updated_at: string;
}

export interface MilestonePlan {
  milestone_id: string;
  name: string;
  planned_amount: number;
  actual_amount: number;
  due_date: string;
  status: 'on_track' | 'delayed' | 'at_risk' | 'completed';
}

export interface B2AConversion {
  conversion_id: string;
  budget_id: string;
  original_category: 'B';
  target_category: 'A';
  amount: number;
  reason: string;
  approved_by?: string;
  status: 'pending' | 'approved' | 'rejected';
  created_at: string;
}

export interface ExpenseReport {
  expense_id: string;
  budget_id: string;
  l3_code: string;
  org_id: string;
  applicant_id: string;
  amount: number;
  expense_date: string;
  description: string;
  control_tag: ControlTag;
  status: ExpenseStatus;
  org_approver_id?: string;
  legal_approver_id?: string;
  org_approved_at?: string;
  legal_approved_at?: string;
  rejected_reason?: string;
  attachments?: string[];
  created_at: string;
  updated_at: string;
}

export interface ApprovalRecord {
  approval_id: string;
  entity_type: 'expense' | 'budget_adjustment' | 'b2a_conversion' | 'alert_closure';
  entity_id: string;
  approval_line: 'org' | 'legal';
  approver_id: string;
  approver_name: string;
  action: 'approve' | 'reject';
  comment?: string;
  created_at: string;
}

export interface AlertRecord {
  alert_id: string;
  alert_level: AlertLevel;
  alert_type: string;
  budget_id?: string;
  org_id: string;
  title: string;
  description: string;
  metric_name?: string;
  metric_value?: number;
  threshold_value?: number;
  deviation_rate?: number;
  status: AlertStatus;
  assigned_to?: string;
  response_deadline?: string;
  responded_at?: string;
  closed_at?: string;
  created_at: string;
  updated_at: string;
}

export interface AlertClosure {
  closure_id: string;
  alert_id: string;
  closure_type: 'action_taken' | 'false_alarm' | 'escalated';
  action_description: string;
  org_signer_id?: string;
  finance_bp_signer_id?: string;
  org_signed_at?: string;
  finance_bp_signed_at?: string;
  created_at: string;
}

export interface AlertEscalation {
  escalation_id: string;
  alert_id: string;
  from_level: AlertLevel;
  to_level: AlertLevel;
  reason: string;
  escalated_at: string;
}

export interface Organization {
  org_id: string;
  org_name: string;
  org_type: 'headquarters' | 'region' | 'subsidiary' | 'department';
  parent_id?: string;
  region?: string;
  finance_bp_id?: string;
  created_at: string;
}

export interface Role {
  role_id: string;
  role_name: string;
  permissions: string[];
  description?: string;
}

export interface GapAnalysis {
  period?: string;
  gap1?: number;
  gap2?: number;
  gap3?: number;
  gap1_detail?: any;
  gap2_detail?: any;
  gap3_detail?: any;
  // Legacy fields
  gap_type?: 'GAP1' | 'GAP2' | 'GAP3';
  title?: string;
  description?: string;
  budget_id?: string;
  org_id?: string;
  metric_name?: string;
  actual_value?: number;
  target_value?: number;
  gap_value?: number;
  gap_rate?: number;
  root_causes?: string[];
  actions?: string[];
}

export interface ListAnalysis {
  list_type: 'LIST1' | 'LIST2' | 'LIST3';
  title: string;
  items: ListAnalysisItem[];
}

export interface ListAnalysisItem {
  item_id: string;
  name: string;
  metric_value: number;
  threshold: number;
  status: 'normal' | 'warning' | 'critical';
  details?: string;
}

export interface ExecutionRate {
  budget_id: string;
  l1_code: string;
  org_id: string;
  annual_amount: number;
  used_amount: number;
  execution_rate: number;
  target_rate: number;
  deviation: number;
  period: string;
}

export interface QuadrantCompliance {
  quadrant: QuadrantType;
  total_budget: number;
  actual_spend: number;
  compliance_rate: number;
  items_count: number;
  compliant_count: number;
}

export interface PdcaRecord {
  pdca_id: string;
  period_type: 'monthly' | 'quarterly' | 'annual';
  period: string;
  org_id: string;
  plan_summary: string;
  do_summary: string;
  check_summary: string;
  act_summary: string;
  budget_deviation?: number;
  alert_count?: number;
  improvement_actions?: string[];
  created_at: string;
  updated_at: string;
}

export interface ReportRecord {
  report_id: string;
  report_type: string;
  period: string;
  org_id?: string;
  title: string;
  content: string;
  deadline: string;
  status: 'draft' | 'submitted' | 'reviewed' | 'finalized';
  generated_at?: string;
  created_at: string;
}

export interface Message {
  id: string;
  role: 'user' | 'assistant' | 'system';
  content: string;
  timestamp: string;
  intent?: Intent;
  routing?: RoutingInfo;
  tools_used?: ToolUsage[];
  suggestions?: string[];
  reasoning_trace?: ReasoningTrace;
  ontology?: import('../services/stream').OntologyMeta;
  isStreaming?: boolean;
}

export interface Intent {
  primary: string;
  confidence: number;
  scene_id?: string;
  sub_intents?: string[];
}

export interface RoutingInfo {
  agent_id: string;
  agent_name: string;
  skill_id?: string;
  routing_reason: string;
}

export interface ToolUsage {
  tool_name: string;
  tool_input: string;
  tool_output: string;
  execution_time_ms: number;
  data_fetched?: number;
  tables_queried?: string[];
}

export interface ReasoningTrace {
  trace_id: string;
  scene: string;
  steps: ReasoningStep[];
  conclusion: string;
  total_time_ms: number;
}

export interface ReasoningStep {
  step_id: string;
  rule_id?: string;
  rule_type?: 'hard' | 'soft' | 'reasoning';
  description: string;
  input: string;
  output: string;
  confidence: number;
  duration_ms: number;
}

export interface SSEEvent {
  event: 'thinking' | 'intent' | 'routing' | 'ontology' | 'content' | 'tools_used' | 'suggestions' | 'done' | 'error';
  data: string;
}

export interface Toast {
  id: string;
  type: 'success' | 'error' | 'warning' | 'info';
  title: string;
  message?: string;
  duration?: number;
}

export interface Badge {
  key: string;
  count: number;
}

export interface ApiResponse<T> {
  success: boolean;
  data: T;
  message?: string;
  error?: string;
}

export interface PaginatedResponse<T> {
  success: boolean;
  data: T[];
  total: number;
  page: number;
  page_size: number;
  message?: string;
}

export interface DashboardSummary {
  total_budget: number;
  total_used: number;
  execution_rate: number;
  active_alerts: number;
  pending_approvals: number;
  budget_by_quadrant: QuadrantCompliance[];
  recent_alerts: AlertRecord[];
  execution_trend: ExecutionRate[];
}

export interface EvalReport {
  report_id: string;
  category: string;
  total_cases: number;
  passed: number;
  failed: number;
  pass_rate: number;
  hard_rule_pass_rate: number;
  soft_rule_pass_rate: number;
  reasoning_rule_pass_rate: number;
  details: EvalResult[];
  created_at: string;
}

export interface EvalResult {
  case_id: string;
  passed: boolean;
  expected: string;
  actual: string;
  trace?: ReasoningTrace;
  error?: string;
}

export interface OntologyObject {
  object_id: string;
  object_type: string;
  name: string;
  properties: Record<string, unknown>;
  relations: OntologyRelation[];
}

export interface OntologyRelation {
  relation_id: string;
  relation_type: string;
  source_id: string;
  target_id: string;
  properties?: Record<string, unknown>;
}

export interface OntologyRule {
  rule_id: string;
  rule_type: 'hard' | 'soft' | 'reasoning';
  name: string;
  description: string;
  parameters?: Record<string, unknown>;
  enabled: boolean;
}

export interface OntologyScene {
  scene_id: string;
  name: string;
  description: string;
  activation_condition: string;
  activated_objects: string[];
  activated_rules: string[];
  activated_behaviors: string[];
}
