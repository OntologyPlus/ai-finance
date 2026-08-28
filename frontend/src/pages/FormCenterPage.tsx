import { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  FileText,
  ClipboardList,
  X,
} from 'lucide-react';
import { clsx } from 'clsx';
import { formApi } from '../services/api';

const TABS = ['表单模板'] as const;

const CATEGORY_MAP: Record<string, { label: string; icon: string; color: string }> = {
  budget: { label: '预算', icon: '💰', color: 'from-brand-500 to-finance-600' },
  expense: { label: '报销', icon: '🧾', color: 'from-compliance-500 to-health-600' },
  alert: { label: '预警', icon: '🚨', color: 'from-alert-500 to-warning-500' },
  analysis: { label: '分析', icon: '📊', color: 'from-purple-500 to-purple-700' },
  pdca: { label: 'PDCA', icon: '🔄', color: 'from-finance-500 to-finance-700' },
  report: { label: '报表', icon: '📋', color: 'from-brand-400 to-brand-600' },
  cycle: { label: '循环', icon: '🔁', color: 'from-surface-500 to-surface-700' },
};

export default function FormCenterPage() {
  const [activeTab, setActiveTab] = useState<typeof TABS[number]>('表单模板');
  const [templates, setTemplates] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedCategory, setSelectedCategory] = useState<string | null>(null);

  // 只读查看模板详情
  const [viewingTemplate, setViewingTemplate] = useState<any | null>(null);

  const fetchData = async () => {
    try {
      const tmplRes = await formApi.getTemplates(selectedCategory ? { category: selectedCategory } : undefined);
      setTemplates(tmplRes.data || []);
    } catch (error) {
      console.error('Failed to fetch form templates:', error);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, [selectedCategory]);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-surface-400">加载中...</div>
      </div>
    );
  }

  // Group templates by category
  const groupedTemplates: Record<string, any[]> = {};
  templates.forEach(t => {
    const cat = t.category || 'other';
    if (!groupedTemplates[cat]) groupedTemplates[cat] = [];
    groupedTemplates[cat].push(t);
  });

  const totalTemplates = templates.length;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-finance-800 font-display">表单中心</h1>
        <p className="text-sm text-surface-400 mt-1">
          表单模板浏览与字段语义查询（提交入口由各业务系统发起，本系统聚焦 AI 解析、合规审查）
        </p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {[
          { label: '表单模板', value: totalTemplates, gradient: 'from-brand-500 to-finance-600' },
          { label: '已分类', value: Object.keys(groupedTemplates).length, gradient: 'from-compliance-500 to-health-600' },
        ].map(card => (
          <div key={card.label} className="glass-card p-5">
            <p className="metric-label mb-2">{card.label}</p>
            <p className="metric-value">
              <span className={`bg-gradient-to-r ${card.gradient} bg-clip-text text-transparent`}>
                {card.value}
              </span>
            </p>
          </div>
        ))}
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
                  layoutId="formTab"
                  className="absolute bottom-0 left-0 right-0 h-0.5 bg-finance-600"
                  transition={{ type: 'spring', stiffness: 500, damping: 30 }}
                />
              )}
            </button>
          ))}
        </div>

        <div className="p-5">
          <AnimatePresence mode="wait">
            {activeTab === '表单模板' && (
              <motion.div
                key="templates"
                initial={{ opacity: 0, y: 4 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -4 }}
                transition={{ duration: 0.15 }}
              >
                {/* Category filter */}
                <div className="flex flex-wrap gap-2 mb-5">
                  <button
                    onClick={() => setSelectedCategory(null)}
                    className={clsx(
                      'px-3 py-1.5 rounded-lg text-xs font-medium transition-colors',
                      !selectedCategory
                        ? 'bg-finance-600 text-white'
                        : 'bg-surface-100 text-surface-600 hover:bg-surface-200'
                    )}
                  >
                    全部
                  </button>
                  {Object.entries(CATEGORY_MAP).map(([key, val]) => (
                    <button
                      key={key}
                      onClick={() => setSelectedCategory(key)}
                      className={clsx(
                        'px-3 py-1.5 rounded-lg text-xs font-medium transition-colors',
                        selectedCategory === key
                          ? 'bg-finance-600 text-white'
                          : 'bg-surface-100 text-surface-600 hover:bg-surface-200'
                      )}
                    >
                      {val.icon} {val.label}
                    </button>
                  ))}
                </div>

                {/* Template cards grouped by category */}
                {Object.entries(groupedTemplates).map(([category, items]) => (
                  <div key={category} className="mb-6">
                    <div className="flex items-center gap-2 mb-3">
                      <span className="text-lg">{CATEGORY_MAP[category]?.icon || '📄'}</span>
                      <h3 className="text-sm font-semibold text-surface-700">
                        {CATEGORY_MAP[category]?.label || category}
                      </h3>
                      <span className="text-xs text-surface-400">({items.length})</span>
                    </div>
                    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
                      {items.map(template => (
                        <div
                          key={template.id}
                          className="p-4 rounded-xl border border-surface-200/60 bg-white hover:border-finance-300 hover:shadow-sm transition-all cursor-pointer group"
                          onClick={() => setViewingTemplate(template)}
                        >
                          <div className="flex items-start gap-3">
                            <div className={clsx(
                              'w-9 h-9 rounded-lg flex items-center justify-center text-white text-sm flex-shrink-0',
                              `bg-gradient-to-br ${CATEGORY_MAP[category]?.color || 'from-surface-400 to-surface-600'}`
                            )}>
                              <FileText size={16} />
                            </div>
                            <div className="flex-1 min-w-0">
                              <p className="text-sm font-medium text-surface-800 group-hover:text-finance-700 transition-colors truncate">
                                {template.form_name}
                              </p>
                              <p className="text-xs text-surface-400 mt-0.5">{template.form_code}</p>
                              {template.description && (
                                <p className="text-xs text-surface-500 mt-1 line-clamp-2">{template.description}</p>
                              )}
                              {template.fields && template.fields.length > 0 && (
                                <p className="text-[10px] text-surface-400 mt-1.5">
                                  字段：{template.fields.length} 个
                                </p>
                              )}
                            </div>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                ))}

                {templates.length === 0 && (
                  <div className="text-center py-10 text-surface-400">
                    <ClipboardList size={40} className="mx-auto mb-3 opacity-30" />
                    <p className="text-sm">暂无表单模板</p>
                  </div>
                )}
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      </div>

      {/* Template Detail (Read-only) Modal */}
      <AnimatePresence>
        {viewingTemplate && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 bg-black/30 flex items-center justify-center z-50"
            onClick={() => setViewingTemplate(null)}
          >
            <motion.div
              initial={{ scale: 0.95, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              exit={{ scale: 0.95, opacity: 0 }}
              className="glass-card p-6 w-full max-w-lg mx-4 max-h-[80vh] overflow-y-auto"
              onClick={e => e.stopPropagation()}
            >
              <div className="flex items-center justify-between mb-4">
                <div>
                  <h3 className="text-lg font-semibold text-finance-800">{viewingTemplate.form_name}</h3>
                  <p className="text-xs text-surface-400 mt-0.5">{viewingTemplate.form_code}</p>
                </div>
                <button onClick={() => setViewingTemplate(null)} className="text-surface-400 hover:text-surface-600">
                  <X size={18} />
                </button>
              </div>

              {viewingTemplate.description && (
                <p className="text-sm text-surface-500 mb-4 p-3 bg-surface-50 rounded-lg">{viewingTemplate.description}</p>
              )}

              <div className="space-y-3">
                <div>
                  <p className="metric-label">分类</p>
                  <p className="text-sm text-surface-800 mt-0.5">
                    {CATEGORY_MAP[viewingTemplate.category]?.icon} {CATEGORY_MAP[viewingTemplate.category]?.label || viewingTemplate.category}
                  </p>
                </div>

                <div>
                  <p className="metric-label mb-2">字段定义（{viewingTemplate.fields?.length || 0} 个）</p>
                  {(!viewingTemplate.fields || viewingTemplate.fields.length === 0) ? (
                    <p className="text-xs text-surface-400 p-3 bg-surface-50 rounded-lg">该模板暂无字段定义</p>
                  ) : (
                    <div className="space-y-1 p-3 bg-surface-50 rounded-xl">
                      {viewingTemplate.fields.map((f: string, idx: number) => (
                        <div key={idx} className="flex items-center gap-2 text-sm">
                          <span className="w-5 h-5 rounded-full bg-finance-100 text-finance-700 text-[10px] font-semibold flex items-center justify-center flex-shrink-0">
                            {idx + 1}
                          </span>
                          <span className="text-surface-800">{f}</span>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              </div>

              <div className="mt-3 p-3 bg-finance-50/50 border border-finance-100 rounded-lg">
                <p className="text-[11px] text-finance-700">
                  提示：本系统仅用于表单模板查询与字段语义分析。表单提交流程由各业务系统（OA / ERP / 财务共享）发起。
                </p>
              </div>

              <div className="flex justify-end mt-5">
                <button onClick={() => setViewingTemplate(null)} className="btn-secondary">
                  关闭
                </button>
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
