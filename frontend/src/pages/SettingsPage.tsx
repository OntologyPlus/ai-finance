import { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Settings as SettingsIcon,
  Building2,
  Users,
  Sliders,
  ChevronDown,
  ChevronRight,
  Shield,
  Plus,
  Pencil,
  Trash2,
  X,
  FileText,
} from 'lucide-react';
import { clsx } from 'clsx';
import { settingsApi } from '../services/api';

const TABS = ['组织架构', '角色管理', '口径映射', '系统配置', '审计日志'] as const;

interface OrgNode {
  org_id: string;
  org_name: string;
  org_type: string;
  parent_id: string | null;
  center_id?: string;
  children: OrgNode[];
}

const ALL_PERMISSIONS = [
  'view_budget',
  'edit_budget',
  'approve_expense',
  'view_expense',
  'edit_expense',
  'view_alert',
  'respond_alert',
  'view_report',
  'edit_settings',
  'manage_users',
];

const PERMISSION_LABELS: Record<string, string> = {
  view_budget: '查看预算',
  edit_budget: '编辑预算',
  approve_expense: '审批费用',
  view_expense: '查看费用',
  edit_expense: '编辑费用',
  view_alert: '查看预警',
  respond_alert: '响应预警',
  view_report: '查看报表',
  edit_settings: '编辑设置',
  manage_users: '管理用户',
};

function OrgTree({
  node,
  depth = 0,
  onEdit,
  onDelete,
}: {
  node: OrgNode;
  depth?: number;
  onEdit: (node: OrgNode) => void;
  onDelete: (node: OrgNode) => void;
}) {
  const [expanded, setExpanded] = useState(depth < 2);
  const hasChildren = node.children.length > 0;

  return (
    <div>
      <div
        className="flex items-center gap-2 px-3 py-2 rounded-lg hover:bg-finance-50/50 transition-colors group"
        style={{ paddingLeft: `${depth * 24 + 12}px` }}
      >
        <button
          onClick={() => hasChildren && setExpanded(!expanded)}
          className="flex items-center gap-2 flex-1 text-left"
        >
          {hasChildren ? (
            expanded ? <ChevronDown size={14} className="text-surface-400" /> : <ChevronRight size={14} className="text-surface-400" />
          ) : (
            <span className="w-3.5" />
          )}
          <Building2 size={14} className={depth === 0 ? 'text-finance-600' : 'text-surface-400'} />
          <span className={clsx('text-sm', depth === 0 ? 'text-finance-800 font-medium' : 'text-surface-700')}>{node.org_name}</span>
          <span className="text-xs text-surface-400">{node.org_id}</span>
          <span className={clsx(
            'text-[10px] px-1.5 py-0.5 rounded-md font-medium',
            node.org_type === 'headquarters' ? 'bg-finance-50 text-finance-700' :
            node.org_type === 'region' ? 'bg-brand-50 text-brand-700' :
            'bg-surface-100 text-surface-500'
          )}>
            {node.org_type === 'headquarters' ? '总部' : node.org_type === 'region' ? '区域' : '部门'}
          </span>
        </button>
        <div className="hidden group-hover:flex items-center gap-1">
          <button
            onClick={() => onEdit(node)}
            className="p-1 rounded hover:bg-surface-100 text-surface-400 hover:text-finance-600 transition-colors"
          >
            <Pencil size={12} />
          </button>
          <button
            onClick={() => onDelete(node)}
            className="p-1 rounded hover:bg-surface-100 text-surface-400 hover:text-alert-600 transition-colors"
          >
            <Trash2 size={12} />
          </button>
        </div>
      </div>
      <AnimatePresence>
        {expanded && hasChildren && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: 'auto' }}
            exit={{ opacity: 0, height: 0 }}
          >
            {node.children.map(child => (
              <OrgTree key={child.org_id} node={child} depth={depth + 1} onEdit={onEdit} onDelete={onDelete} />
            ))}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

function DeptModal({
  dept,
  onClose,
  onSave,
}: {
  dept?: OrgNode | null;
  onClose: () => void;
  onSave: (data: { dept_id: string; dept_name: string; center_id?: string; parent_dept_id?: string }) => void;
}) {
  const [form, setForm] = useState({
    dept_id: dept?.org_id || '',
    dept_name: dept?.org_name || '',
    center_id: dept?.center_id || '',
    parent_dept_id: dept?.parent_id || '',
  });
  const isEdit = !!dept;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30" onClick={onClose}>
      <motion.div
        initial={{ opacity: 0, scale: 0.95 }}
        animate={{ opacity: 1, scale: 1 }}
        exit={{ opacity: 0, scale: 0.95 }}
        className="bg-white rounded-xl shadow-xl p-6 w-full max-w-md"
        onClick={e => e.stopPropagation()}
      >
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-lg font-semibold text-surface-800">{isEdit ? '编辑部门' : '新增部门'}</h3>
          <button onClick={onClose} className="text-surface-400 hover:text-surface-600">
            <X size={18} />
          </button>
        </div>
        <div className="space-y-3">
          <div>
            <label className="block text-xs text-surface-500 mb-1">部门ID</label>
            <input
              type="text"
              value={form.dept_id}
              onChange={e => setForm(prev => ({ ...prev, dept_id: e.target.value }))}
              disabled={isEdit}
              className="w-full px-3 py-2 rounded-lg border border-surface-200 bg-white text-sm focus:outline-none focus:ring-2 focus:ring-finance-500/20 focus:border-finance-500 disabled:bg-surface-50"
            />
          </div>
          <div>
            <label className="block text-xs text-surface-500 mb-1">部门名称</label>
            <input
              type="text"
              value={form.dept_name}
              onChange={e => setForm(prev => ({ ...prev, dept_name: e.target.value }))}
              className="w-full px-3 py-2 rounded-lg border border-surface-200 bg-white text-sm focus:outline-none focus:ring-2 focus:ring-finance-500/20 focus:border-finance-500"
            />
          </div>
          <div>
            <label className="block text-xs text-surface-500 mb-1">归属中心</label>
            <input
              type="text"
              value={form.center_id}
              onChange={e => setForm(prev => ({ ...prev, center_id: e.target.value }))}
              className="w-full px-3 py-2 rounded-lg border border-surface-200 bg-white text-sm focus:outline-none focus:ring-2 focus:ring-finance-500/20 focus:border-finance-500"
            />
          </div>
          <div>
            <label className="block text-xs text-surface-500 mb-1">上级部门ID</label>
            <input
              type="text"
              value={form.parent_dept_id}
              onChange={e => setForm(prev => ({ ...prev, parent_dept_id: e.target.value }))}
              className="w-full px-3 py-2 rounded-lg border border-surface-200 bg-white text-sm focus:outline-none focus:ring-2 focus:ring-finance-500/20 focus:border-finance-500"
            />
          </div>
        </div>
        <div className="flex justify-end gap-2 mt-5">
          <button onClick={onClose} className="px-4 py-2 text-sm text-surface-600 hover:text-surface-800 transition-colors">
            取消
          </button>
          <button
            onClick={() => onSave(form)}
            className="btn-primary text-sm"
          >
            {isEdit ? '保存' : '创建'}
          </button>
        </div>
      </motion.div>
    </div>
  );
}

export default function SettingsPage() {
  const [settings, setSettings] = useState<any>(null);
  const [organization, setOrganization] = useState<any[]>([]);
  const [roles, setRoles] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState<typeof TABS[number]>('组织架构');
  const [configs, setConfigs] = useState<Record<string, string>>({});
  const [auditLog, setAuditLog] = useState<any[]>([]);
  const [showDeptModal, setShowDeptModal] = useState(false);
  const [editingDept, setEditingDept] = useState<OrgNode | null>(null);
  const [expandedRole, setExpandedRole] = useState<string | null>(null);
  const [rolePermissions, setRolePermissions] = useState<Record<string, string[]>>({});
  const [caliberMappings, setCaliberMappings] = useState<any[]>([]);
  const [editingMappingId, setEditingMappingId] = useState<string | null>(null);
  const [editFormula, setEditFormula] = useState('');

  useEffect(() => {
    const fetchAll = async () => {
      try {
        const [settingsRes, orgRes, rolesRes] = await Promise.all([
          settingsApi.getSettings(),
          settingsApi.getOrganization(),
          settingsApi.getRoles(),
        ]);
        setSettings(settingsRes.data || null);
        const orgData = orgRes.data;
        const orgList = Array.isArray(orgData?.departments) ? orgData.departments : Array.isArray(orgData) ? orgData : [];
        setOrganization(orgList);
        setRoles(rolesRes.data || []);
        if (settingsRes.data?.configs && Array.isArray(settingsRes.data.configs)) {
          const configMap: Record<string, string> = {};
          settingsRes.data.configs.forEach((c: any) => {
            configMap[c.key] = c.value;
          });
          setConfigs(configMap);
        }
        // Parse role permissions
        const permMap: Record<string, string[]> = {};
        (rolesRes.data || []).forEach((r: any) => {
          const perms = r.permissions;
          if (typeof perms === 'string') {
            try {
              permMap[r.role_id] = JSON.parse(perms);
            } catch {
              permMap[r.role_id] = [];
            }
          } else if (Array.isArray(perms)) {
            permMap[r.role_id] = perms;
          } else {
            permMap[r.role_id] = [];
          }
        });
        setRolePermissions(permMap);
      } catch {
      } finally {
        setLoading(false);
      }
    };
    fetchAll();
  }, []);

  useEffect(() => {
    if (activeTab === '审计日志') {
      settingsApi.getAuditLog(50).then(res => {
        setAuditLog(res.data || []);
      }).catch(() => {});
    }
    if (activeTab === '口径映射') {
      settingsApi.getCaliberMappings().then(res => {
        setCaliberMappings(res.data || []);
      }).catch(() => {});
    }
  }, [activeTab]);

  const handleSave = async () => {
    try {
      await settingsApi.updateSettings(configs);
    } catch {}
  };

  const handleCreateDept = async (data: { dept_id: string; dept_name: string; center_id?: string; parent_dept_id?: string }) => {
    try {
      await settingsApi.createDepartment(data);
      setShowDeptModal(false);
      // Refresh organization
      const orgRes = await settingsApi.getOrganization();
      const orgData = orgRes.data;
      const orgList = Array.isArray(orgData?.departments) ? orgData.departments : Array.isArray(orgData) ? orgData : [];
      setOrganization(orgList);
    } catch {}
  };

  const handleEditDept = async (data: { dept_id: string; dept_name: string; center_id?: string; parent_dept_id?: string }) => {
    try {
      await settingsApi.updateDepartment(data.dept_id, data);
      setEditingDept(null);
      const orgRes = await settingsApi.getOrganization();
      const orgData = orgRes.data;
      const orgList = Array.isArray(orgData?.departments) ? orgData.departments : Array.isArray(orgData) ? orgData : [];
      setOrganization(orgList);
    } catch {}
  };

  const handleDeleteDept = async (node: OrgNode) => {
    if (!confirm(`确定删除部门 "${node.org_name}" 吗？`)) return;
    try {
      await settingsApi.deleteDepartment(node.org_id);
      const orgRes = await settingsApi.getOrganization();
      const orgData = orgRes.data;
      const orgList = Array.isArray(orgData?.departments) ? orgData.departments : Array.isArray(orgData) ? orgData : [];
      setOrganization(orgList);
    } catch {}
  };

  const handleTogglePermission = async (roleId: string, permission: string) => {
    const current = rolePermissions[roleId] || [];
    const updated = current.includes(permission)
      ? current.filter(p => p !== permission)
      : [...current, permission];
    setRolePermissions(prev => ({ ...prev, [roleId]: updated }));
    try {
      await settingsApi.updateRolePermissions(roleId, updated);
    } catch {}
  };

  const configItems = settings?.configs || [];
  const categories = [...new Set(configItems.map((c: any) => c.category))];

  const buildOrgTree = (orgs: any[]): OrgNode[] => {
    if (!Array.isArray(orgs)) return [];
    const map = new Map<string, OrgNode>();
    const roots: OrgNode[] = [];
    orgs.forEach((org: any) => {
      const orgId = org.dept_id || org.org_id;
      const parentId = org.parent_dept_id || org.parent_id || null;
      const orgType = !parentId ? 'headquarters' : org.center_id === orgId ? 'region' : 'department';
      map.set(orgId, {
        org_id: orgId,
        org_name: org.dept_name || org.org_name || '',
        org_type: orgType,
        parent_id: parentId,
        center_id: org.center_id,
        children: [],
      });
    });
    orgs.forEach((org: any) => {
      const orgId = org.dept_id || org.org_id;
      const parentId = org.parent_dept_id || org.parent_id || null;
      const node = map.get(orgId)!;
      if (parentId && map.has(parentId)) {
        map.get(parentId)!.children.push(node);
      } else {
        roots.push(node);
      }
    });
    return roots;
  };

  const orgTree = buildOrgTree(organization);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-finance-800 font-display">系统设置</h1>
        <p className="text-sm text-surface-400 mt-1">组织架构、角色权限与系统配置管理</p>
      </div>

      <div className="glass-card">
        <div className="flex border-b border-surface-200/60">
          {TABS.map(tab => (
            <button
              key={tab}
              onClick={() => setActiveTab(tab)}
              className={clsx(
                'px-5 py-3 text-sm font-medium transition-colors relative',
                activeTab === tab ? 'text-finance-700' : 'text-surface-400 hover:text-surface-600'
              )}
            >
              {tab}
              {activeTab === tab && (
                <motion.div
                  layoutId="settingsTab"
                  className="absolute bottom-0 left-0 right-0 h-0.5 bg-finance-600"
                  transition={{ type: 'spring', stiffness: 500, damping: 30 }}
                />
              )}
            </button>
          ))}
        </div>

        <div className="p-5">
          {loading ? (
            <div className="flex items-center justify-center py-12 text-surface-400">加载中...</div>
          ) : (
            <AnimatePresence mode="wait">
              {activeTab === '组织架构' && (
                <motion.div
                  key="org"
                  initial={{ opacity: 0, y: 4 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: -4 }}
                  transition={{ duration: 0.15 }}
                >
                  <div className="flex justify-end mb-3">
                    <button
                      onClick={() => { setEditingDept(null); setShowDeptModal(true); }}
                      className="btn-primary text-xs"
                    >
                      <Plus size={12} /> 新增部门
                    </button>
                  </div>
                  <div className="glass-card-static p-4">
                    {orgTree.map(node => (
                      <OrgTree
                        key={node.org_id}
                        node={node}
                        onEdit={(n) => { setEditingDept(n); setShowDeptModal(true); }}
                        onDelete={handleDeleteDept}
                      />
                    ))}
                  </div>
                  {showDeptModal && (
                    <DeptModal
                      dept={editingDept}
                      onClose={() => { setShowDeptModal(false); setEditingDept(null); }}
                      onSave={editingDept ? handleEditDept : handleCreateDept}
                    />
                  )}
                </motion.div>
              )}

              {activeTab === '角色管理' && (
                <motion.div
                  key="roles"
                  initial={{ opacity: 0, y: 4 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: -4 }}
                  transition={{ duration: 0.15 }}
                >
                  <div className="space-y-3">
                    {roles.map((role: any) => {
                      const isExpanded = expandedRole === role.role_id;
                      const perms = rolePermissions[role.role_id] || [];
                      return (
                        <div key={role.role_id} className="glass-card-static">
                          <button
                            onClick={() => setExpandedRole(isExpanded ? null : role.role_id)}
                            className="w-full p-4 flex items-center justify-between text-left"
                          >
                            <div className="flex items-center gap-3">
                              <Shield size={14} className="text-finance-500" />
                              <span className="font-mono text-xs text-finance-700">{role.role_id}</span>
                              <span className="font-medium text-surface-800">{role.role_name}</span>
                            </div>
                            <div className="flex items-center gap-3 text-xs text-surface-400">
                              <span>{perms.length} 权限</span>
                              <span>·</span>
                              <span>{role.users_count || 0} 用户</span>
                              {isExpanded ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
                            </div>
                          </button>
                          <p className="px-4 pb-2 text-sm text-surface-500">{role.description}</p>
                          <AnimatePresence>
                            {isExpanded && (
                              <motion.div
                                initial={{ opacity: 0, height: 0 }}
                                animate={{ opacity: 1, height: 'auto' }}
                                exit={{ opacity: 0, height: 0 }}
                                className="px-4 pb-4"
                              >
                                <div className="border-t border-surface-100 pt-3">
                                  <h5 className="text-xs font-semibold text-surface-600 mb-2">权限配置</h5>
                                  <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-2">
                                    {ALL_PERMISSIONS.map(perm => (
                                      <label
                                        key={perm}
                                        className={clsx(
                                          'flex items-center gap-2 px-3 py-2 rounded-lg border cursor-pointer transition-colors text-sm',
                                          perms.includes(perm)
                                            ? 'border-finance-300 bg-finance-50/50 text-finance-700'
                                            : 'border-surface-200 bg-white text-surface-500 hover:border-surface-300'
                                        )}
                                      >
                                        <input
                                          type="checkbox"
                                          checked={perms.includes(perm)}
                                          onChange={() => handleTogglePermission(role.role_id, perm)}
                                          className="rounded border-surface-300 text-finance-600 focus:ring-finance-500"
                                        />
                                        <span className="text-xs">{PERMISSION_LABELS[perm] || perm}</span>
                                      </label>
                                    ))}
                                  </div>
                                </div>
                              </motion.div>
                            )}
                          </AnimatePresence>
                        </div>
                      );
                    })}
                  </div>
                </motion.div>
              )}

              {activeTab === '口径映射' && (
                <motion.div
                  key="caliber"
                  initial={{ opacity: 0, y: 4 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: -4 }}
                  transition={{ duration: 0.15 }}
                >
                  <div className="flex items-center justify-between mb-3">
                    <div className="flex items-center gap-2 text-sm text-surface-600">
                      <Sliders size={14} className="text-finance-500" />
                      口径映射规则配置
                    </div>
                    <button
                      onClick={() => {
                        settingsApi.getCaliberMappings().then(res => {
                          setCaliberMappings(res.data || []);
                        }).catch(() => {});
                      }}
                      className="text-xs text-finance-600 hover:text-finance-800 transition-colors"
                    >
                      刷新
                    </button>
                  </div>
                  {caliberMappings.length === 0 ? (
                    <div className="text-center py-12 text-surface-400 text-sm">暂无口径映射数据</div>
                  ) : (
                    <div className="overflow-x-auto">
                      <table className="w-full text-sm">
                        <thead>
                          <tr className="border-b border-surface-200">
                            <th className="text-left py-2 px-3 text-xs font-medium text-surface-500">财务代码</th>
                            <th className="text-left py-2 px-3 text-xs font-medium text-surface-500">财务名称</th>
                            <th className="text-left py-2 px-3 text-xs font-medium text-surface-500">管理代码</th>
                            <th className="text-left py-2 px-3 text-xs font-medium text-surface-500">管理名称</th>
                            <th className="text-left py-2 px-3 text-xs font-medium text-surface-500">转换规则</th>
                            <th className="text-left py-2 px-3 text-xs font-medium text-surface-500">调整公式</th>
                            <th className="text-left py-2 px-3 text-xs font-medium text-surface-500">差异说明</th>
                          </tr>
                        </thead>
                        <tbody>
                          {caliberMappings.map((m: any) => (
                            <tr key={m.mapping_id} className="border-b border-surface-100 hover:bg-surface-50/50">
                              <td className="py-2 px-3 font-mono text-xs text-finance-600">{m.financial_code}</td>
                              <td className="py-2 px-3 text-surface-700">{m.financial_name}</td>
                              <td className="py-2 px-3 font-mono text-xs text-finance-600">{m.management_code}</td>
                              <td className="py-2 px-3 text-surface-700">{m.management_name}</td>
                              <td className="py-2 px-3">
                                <span className="text-[10px] px-1.5 py-0.5 rounded-md font-medium bg-surface-100 text-surface-600">
                                  {m.conversion_rule}
                                </span>
                              </td>
                              <td className="py-2 px-3">
                                {editingMappingId === m.mapping_id ? (
                                  <div className="flex items-center gap-1">
                                    <input
                                      type="text"
                                      value={editFormula}
                                      onChange={e => setEditFormula(e.target.value)}
                                      className="w-40 px-2 py-1 rounded border border-finance-300 text-xs font-mono focus:outline-none focus:ring-2 focus:ring-finance-500/20"
                                    />
                                    <button
                                      onClick={async () => {
                                        try {
                                          await settingsApi.updateCaliberMappings([{
                                            mapping_id: m.mapping_id,
                                            adjustment_formula: editFormula,
                                          }]);
                                          setCaliberMappings(prev =>
                                            prev.map(item =>
                                              item.mapping_id === m.mapping_id
                                                ? { ...item, adjustment_formula: editFormula }
                                                : item
                                            )
                                          );
                                          setEditingMappingId(null);
                                        } catch {}
                                      }}
                                      className="px-2 py-1 text-xs bg-finance-600 text-white rounded hover:bg-finance-700"
                                    >
                                      保存
                                    </button>
                                    <button
                                      onClick={() => setEditingMappingId(null)}
                                      className="px-2 py-1 text-xs text-surface-500 hover:text-surface-700"
                                    >
                                      取消
                                    </button>
                                  </div>
                                ) : (
                                  <span
                                    className="font-mono text-xs text-surface-700 cursor-pointer hover:text-finance-600 hover:underline"
                                    title="点击编辑"
                                    onClick={() => {
                                      setEditingMappingId(m.mapping_id);
                                      setEditFormula(m.adjustment_formula || '');
                                    }}
                                  >
                                    {m.adjustment_formula || '-'}
                                  </span>
                                )}
                              </td>
                              <td className="py-2 px-3 text-xs text-surface-500 max-w-[200px] truncate" title={m.difference_note}>
                                {m.difference_note || '-'}
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  )}
                </motion.div>
              )}

              {activeTab === '系统配置' && (
                <motion.div
                  key="config"
                  initial={{ opacity: 0, y: 4 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: -4 }}
                  transition={{ duration: 0.15 }}
                >
                  <div className="space-y-6">
                    {categories.map((category: string) => (
                      <div key={category}>
                        <h3 className="text-sm font-semibold text-surface-700 mb-3 flex items-center gap-2">
                          <Sliders size={14} className="text-finance-500" />
                          {category}
                        </h3>
                        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
                          {configItems.filter((c: any) => c.category === category).map((config: any) => (
                            <div key={config.key} className="p-3 rounded-lg bg-surface-50">
                              <label className="block text-xs text-surface-500 mb-1.5">{config.label}</label>
                              {config.type === 'select' ? (
                                <select
                                  value={configs[config.key] || ''}
                                  onChange={e => setConfigs(prev => ({ ...prev, [config.key]: e.target.value }))}
                                  className="w-full px-2.5 py-1.5 rounded-lg border border-surface-200 bg-white text-sm focus:outline-none focus:ring-2 focus:ring-finance-500/20 focus:border-finance-500"
                                >
                                  {config.options?.map((opt: string) => (
                                    <option key={opt} value={opt}>{opt}</option>
                                  ))}
                                </select>
                              ) : (
                                <input
                                  type={config.type}
                                  value={configs[config.key] || ''}
                                  onChange={e => setConfigs(prev => ({ ...prev, [config.key]: e.target.value }))}
                                  className="w-full px-2.5 py-1.5 rounded-lg border border-surface-200 bg-white text-sm font-mono focus:outline-none focus:ring-2 focus:ring-finance-500/20 focus:border-finance-500"
                                />
                              )}
                            </div>
                          ))}
                        </div>
                      </div>
                    ))}
                    <div className="flex justify-end">
                      <button className="btn-primary" onClick={handleSave}>
                        保存配置
                      </button>
                    </div>
                  </div>
                </motion.div>
              )}

              {activeTab === '审计日志' && (
                <motion.div
                  key="audit"
                  initial={{ opacity: 0, y: 4 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: -4 }}
                  transition={{ duration: 0.15 }}
                >
                  <div className="flex items-center justify-between mb-3">
                    <div className="flex items-center gap-2 text-sm text-surface-600">
                      <FileText size={14} className="text-finance-500" />
                      最近操作记录
                    </div>
                    <button
                      onClick={() => {
                        settingsApi.getAuditLog(50).then(res => setAuditLog(res.data || [])).catch(() => {});
                      }}
                      className="text-xs text-finance-600 hover:text-finance-800 transition-colors"
                    >
                      刷新
                    </button>
                  </div>
                  {auditLog.length === 0 ? (
                    <div className="text-center py-12 text-surface-400 text-sm">暂无审计日志</div>
                  ) : (
                    <div className="overflow-x-auto">
                      <table className="w-full text-sm">
                        <thead>
                          <tr className="border-b border-surface-200">
                            <th className="text-left py-2 px-3 text-xs font-medium text-surface-500">时间</th>
                            <th className="text-left py-2 px-3 text-xs font-medium text-surface-500">用户</th>
                            <th className="text-left py-2 px-3 text-xs font-medium text-surface-500">操作</th>
                            <th className="text-left py-2 px-3 text-xs font-medium text-surface-500">目标</th>
                            <th className="text-left py-2 px-3 text-xs font-medium text-surface-500">详情</th>
                          </tr>
                        </thead>
                        <tbody>
                          {auditLog.map((entry: any, i: number) => (
                            <tr key={i} className="border-b border-surface-100 hover:bg-surface-50/50">
                              <td className="py-2 px-3 text-xs text-surface-400 font-mono">{entry.timestamp}</td>
                              <td className="py-2 px-3 text-surface-700">{entry.user}</td>
                              <td className="py-2 px-3">
                                <span className={clsx(
                                  'text-[10px] px-1.5 py-0.5 rounded-md font-medium',
                                  entry.action.includes('创建') ? 'bg-compliance-50 text-compliance-700' :
                                  entry.action.includes('删除') ? 'bg-alert-50 text-alert-700' :
                                  entry.action.includes('更新') ? 'bg-warning-50 text-warning-700' :
                                  'bg-surface-100 text-surface-600'
                                )}>
                                  {entry.action}
                                </span>
                              </td>
                              <td className="py-2 px-3 font-mono text-xs text-finance-600">{entry.target}</td>
                              <td className="py-2 px-3 text-xs text-surface-500 max-w-[200px] truncate">{entry.details}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  )}
                </motion.div>
              )}
            </AnimatePresence>
          )}
        </div>
      </div>
    </div>
  );
}
