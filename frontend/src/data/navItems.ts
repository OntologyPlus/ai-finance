import {
  LayoutDashboard,
  Bot,
  Wallet,
  Receipt,
  CheckSquare,
  AlertTriangle,
  BarChart3,
  RotateCcw,
  FileText,
  Network,
  Settings,
  Target,
  ClipboardList,
  FileSignature,
  Droplets,
  Layers,
  ShieldCheck,
  FlaskConical,
  Users,
  GitBranch,
  Brain,
  type LucideIcon,
} from 'lucide-react';

export interface NavItem {
  id: string;
  label: string;
  icon: LucideIcon;
  path: string;
  badgeKey?: string;
}

export interface NavSection {
  title: string;
  items: NavItem[];
}

export const navSections: NavSection[] = [
  {
    title: '概览',
    items: [
      {
        id: 'dashboard',
        label: '驾驶舱',
        icon: LayoutDashboard,
        path: '/dashboard',
      },
      {
        id: 'ai-agent',
        label: 'AI 助手',
        icon: Bot,
        path: '/ai-agent',
      },
    ],
  },
  {
    title: '业务',
    items: [
      {
        id: 'budget',
        label: '预算管理',
        icon: Wallet,
        path: '/budget',
      },
      {
        id: 'expense',
        label: '费用报销',
        icon: Receipt,
        path: '/expense',
        badgeKey: 'pending_expenses',
      },
      {
        id: 'approval',
        label: '审批工作台',
        icon: CheckSquare,
        path: '/approval',
        badgeKey: 'pending_approvals',
      },
      {
        id: 'alert',
        label: '预警中心',
        icon: AlertTriangle,
        path: '/alert',
        badgeKey: 'active_alerts',
      },
      {
        id: 'strategic',
        label: '战略意图',
        icon: Target,
        path: '/strategic',
      },
      {
        id: 'forms',
        label: '表单中心',
        icon: ClipboardList,
        path: '/forms',
      },
      {
        id: 'cashflow',
        label: '现金流监控',
        icon: Droplets,
        path: '/cashflow',
      },
      {
        id: 'scenario',
        label: '情景规划',
        icon: Layers,
        path: '/scenario',
      },
      {
        id: 'hcp',
        label: 'HCP合规',
        icon: ShieldCheck,
        path: '/hcp',
      },
    ],
  },
  {
    title: '分析',
    items: [
      {
        id: 'analysis',
        label: '经营分析',
        icon: BarChart3,
        path: '/analysis',
      },
      {
        id: 'pdca',
        label: 'PDCA 复盘',
        icon: RotateCcw,
        path: '/pdca',
      },
      {
        id: 'report',
        label: '报表中心',
        icon: FileText,
        path: '/report',
      },
      {
        id: 'business-review',
        label: '经营分析会',
        icon: Users,
        path: '/business-review',
      },
    ],
  },
  {
    title: '管理',
    items: [
      {
        id: 'ontology',
        label: '本体管理',
        icon: Network,
        path: '/ontology',
      },
      {
        id: 'impact',
        label: '影响力评估',
        icon: GitBranch,
        path: '/impact',
      },
      {
        id: 'auditor',
        label: '推理审计员',
        icon: Brain,
        path: '/auditor',
      },
      {
        id: 'settings',
        label: '系统设置',
        icon: Settings,
        path: '/settings',
      },
    ],
  },
];
