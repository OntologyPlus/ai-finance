import { create } from 'zustand';
import type {
  BudgetItem,
  ExpenseReport,
  ApprovalRecord,
  AlertRecord,
  Message,
  Toast,
  Badge,
} from '../types';

export interface AuthUser {
  user_id: string;
  username: string;
  display_name: string;
  role: string;
  center_id?: string;
  department_id?: string;
}

export interface AIContext {
  lastTopic: string;       // 上次讨论的主题
  lastInsight: string;     // 上次的 AI 发现
  trackedItems: string[];  // 正在跟踪的事项
  lastUpdate: string;      // 最后更新时间
}

interface AppState {
  budgets: BudgetItem[];
  expenses: ExpenseReport[];
  approvals: ApprovalRecord[];
  alerts: AlertRecord[];
  messages: Message[];
  badges: Badge[];
  toasts: Toast[];
  activeTab: string;
  sidebarCollapsed: boolean;
  currentSessionId: string | null;
  aiContext: AIContext | null;

  // Auth state
  token: string | null;
  user: AuthUser | null;
  isAuthenticated: boolean;

  setBudgets: (budgets: BudgetItem[]) => void;
  addBudget: (budget: BudgetItem) => void;
  updateBudget: (budgetId: string, budget: Partial<BudgetItem>) => void;

  setExpenses: (expenses: ExpenseReport[]) => void;
  addExpense: (expense: ExpenseReport) => void;
  updateExpense: (expenseId: string, expense: Partial<ExpenseReport>) => void;

  setApprovals: (approvals: ApprovalRecord[]) => void;
  addApproval: (approval: ApprovalRecord) => void;

  setAlerts: (alerts: AlertRecord[]) => void;
  addAlert: (alert: AlertRecord) => void;
  updateAlert: (alertId: string, alert: Partial<AlertRecord>) => void;

  setMessages: (messages: Message[]) => void;
  addMessage: (message: Message) => void;
  updateMessage: (messageId: string, message: Partial<Message>) => void;

  setBadges: (badges: Badge[]) => void;
  updateBadge: (key: string, count: number) => void;

  addToast: (toast: Omit<Toast, 'id'>) => void;
  removeToast: (id: string) => void;

  setActiveTab: (tab: string) => void;
  toggleSidebar: () => void;
  setSidebarCollapsed: (collapsed: boolean) => void;
  setCurrentSessionId: (sessionId: string | null) => void;
  setAIContext: (ctx: AIContext | null) => void;

  // Auth actions
  login: (token: string, user: AuthUser) => void;
  logout: () => void;
  updateUser: (user: AuthUser) => void;
}

function restoreAuth(): { token: string | null; user: AuthUser | null; isAuthenticated: boolean } {
  try {
    const token = localStorage.getItem('auth_token');
    const userStr = localStorage.getItem('auth_user');
    if (token && userStr) {
      const user = JSON.parse(userStr) as AuthUser;
      return { token, user, isAuthenticated: true };
    }
  } catch {
    // ignore parse errors
  }
  return { token: null, user: null, isAuthenticated: false };
}

const restoredAuth = restoreAuth();

export const useAppStore = create<AppState>((set) => ({
  budgets: [],
  expenses: [],
  approvals: [],
  alerts: [],
  messages: [],
  badges: [],
  toasts: [],
  activeTab: 'dashboard',
  sidebarCollapsed: false,
  currentSessionId: null,
  aiContext: null,

  // Auth state (restored from localStorage)
  token: restoredAuth.token,
  user: restoredAuth.user,
  isAuthenticated: restoredAuth.isAuthenticated,

  setBudgets: (budgets) => set({ budgets }),
  addBudget: (budget) => set((state) => ({ budgets: [...state.budgets, budget] })),
  updateBudget: (budgetId, budget) =>
    set((state) => ({
      budgets: state.budgets.map((b) => (b.budget_id === budgetId ? { ...b, ...budget } : b)),
    })),

  setExpenses: (expenses) => set({ expenses }),
  addExpense: (expense) => set((state) => ({ expenses: [...state.expenses, expense] })),
  updateExpense: (expenseId, expense) =>
    set((state) => ({
      expenses: state.expenses.map((e) => (e.expense_id === expenseId ? { ...e, ...expense } : e)),
    })),

  setApprovals: (approvals) => set({ approvals }),
  addApproval: (approval) => set((state) => ({ approvals: [...state.approvals, approval] })),

  setAlerts: (alerts) => set({ alerts }),
  addAlert: (alert) => set((state) => ({ alerts: [...state.alerts, alert] })),
  updateAlert: (alertId, alert) =>
    set((state) => ({
      alerts: state.alerts.map((a) => (a.alert_id === alertId ? { ...a, ...alert } : a)),
    })),

  setMessages: (messages) => set({ messages }),
  addMessage: (message) => set((state) => ({ messages: [...state.messages, message] })),
  updateMessage: (messageId, message) =>
    set((state) => ({
      messages: state.messages.map((m) => (m.id === messageId ? { ...m, ...message } : m)),
    })),

  setBadges: (badges) => set({ badges }),
  updateBadge: (key, count) =>
    set((state) => {
      const existing = state.badges.find((b) => b.key === key);
      if (existing) {
        return {
          badges: state.badges.map((b) => (b.key === key ? { ...b, count } : b)),
        };
      }
      return { badges: [...state.badges, { key, count }] };
    }),

  addToast: (toast) =>
    set((state) => {
      const id = crypto.randomUUID();
      const duration = toast.duration ?? 3000;
      setTimeout(() => {
        useAppStore.getState().removeToast(id);
      }, duration);
      return { toasts: [...state.toasts, { ...toast, id }] };
    }),
  removeToast: (id) =>
    set((state) => ({
      toasts: state.toasts.filter((t) => t.id !== id),
    })),

  setActiveTab: (tab) => set({ activeTab: tab }),
  toggleSidebar: () => set((state) => ({ sidebarCollapsed: !state.sidebarCollapsed })),
  setSidebarCollapsed: (collapsed) => set({ sidebarCollapsed: collapsed }),
  setCurrentSessionId: (sessionId) => set({ currentSessionId: sessionId }),
  setAIContext: (ctx) => set({ aiContext: ctx }),

  // Auth actions
  login: (token, user) => {
    localStorage.setItem('auth_token', token);
    localStorage.setItem('auth_user', JSON.stringify(user));
    set({ token, user, isAuthenticated: true });
  },
  logout: () => {
    localStorage.removeItem('auth_token');
    localStorage.removeItem('auth_user');
    set({ token: null, user: null, isAuthenticated: false });
  },
  updateUser: (user) => {
    localStorage.setItem('auth_user', JSON.stringify(user));
    set({ user });
  },
}));
