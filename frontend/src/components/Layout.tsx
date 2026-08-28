import { useState, useEffect } from 'react';
import { useLocation, useNavigate, Outlet } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Bell,
  User,
  ChevronLeft,
  ChevronRight,
  X,
  LogOut,
} from 'lucide-react';
import { navSections } from '../data/navItems';
import { useAppStore } from '../store';
import AIStatusBar from './ai/AIStatusBar';
import ProactiveInsightBanner from './ai/ProactiveInsightBanner';

export default function Layout() {
  const location = useLocation();
  const navigate = useNavigate();
  const { sidebarCollapsed, toggleSidebar, badges, toasts, removeToast, user, logout } = useAppStore();
  const [hoveredItem, setHoveredItem] = useState<string | null>(null);

  const currentPath = location.pathname;
  const totalBadgeCount = badges.reduce((sum, b) => sum + b.count, 0);

  useEffect(() => {
    if (toasts.length > 0) {
      const timer = setTimeout(() => {
        removeToast(toasts[0].id);
      }, toasts[0].duration || 4000);
      return () => clearTimeout(timer);
    }
  }, [toasts, removeToast]);

  const getBadgeCount = (key?: string): number => {
    if (!key) return 0;
    const badge = badges.find((b) => b.key === key);
    return badge?.count || 0;
  };

  return (
    <div className="flex h-screen overflow-hidden bg-surface-50">
      {/* v10.0: 删除 ambient-bg 漂移背景 */}

      <motion.aside
        initial={false}
        animate={{ width: sidebarCollapsed ? 64 : 240 }}
        transition={{ duration: 0.2, ease: 'easeInOut' }}
        className="relative flex flex-col border-r border-surface-200 bg-white z-20"
      >
        <div className="flex items-center h-16 px-4 border-b border-surface-200/60">
          <AnimatePresence mode="wait">
            {!sidebarCollapsed && (
              <motion.div
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                transition={{ duration: 0.15 }}
                className="flex items-center gap-3"
              >
                <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-brand-500 to-finance-700 flex items-center justify-center">
                  <span className="text-white font-bold text-sm">F</span>
                </div>
                <div>
                  <h1 className="text-sm font-bold text-finance-800 font-display">AI-Finance</h1>
                  <p className="text-[10px] text-surface-400">财经管理AI原生系统</p>
                </div>
              </motion.div>
            )}
          </AnimatePresence>
          {sidebarCollapsed && (
            <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-brand-500 to-finance-700 flex items-center justify-center mx-auto">
              <span className="text-white font-bold text-sm">F</span>
            </div>
          )}
        </div>

        <nav className="flex-1 overflow-y-auto py-4 px-2">
          {navSections.map((section) => (
            <div key={section.title} className="mb-6">
              {!sidebarCollapsed && (
                <p className="px-3 mb-2 text-[10px] font-semibold uppercase tracking-widest text-surface-400">
                  {section.title}
                </p>
              )}
              <div className="space-y-0.5">
                {section.items.map((item) => {
                  const isActive = currentPath === item.path;
                  const badgeCount = getBadgeCount(item.badgeKey);
                  const Icon = item.icon;

                  return (
                    <motion.button
                      key={item.id}
                      onClick={() => navigate(item.path)}
                      onMouseEnter={() => setHoveredItem(item.id)}
                      onMouseLeave={() => setHoveredItem(null)}
                      className={`
                        relative w-full flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-medium transition-all duration-150
                        ${isActive
                          ? 'bg-brand-50 text-brand-700'
                          : 'text-surface-600 hover:bg-surface-100 hover:text-surface-800'
                        }
                      `}
                      whileHover={{ x: 2 }}
                      whileTap={{ scale: 0.98 }}
                    >
                      {isActive && (
                        <motion.div
                          layoutId="activeNav"
                          className="absolute left-0 top-1/2 -translate-y-1/2 w-[3px] h-5 bg-brand-500 rounded-r-full"
                          transition={{ type: 'spring', stiffness: 500, damping: 30 }}
                        />
                      )}
                      <Icon
                        size={18}
                        className={`flex-shrink-0 ${isActive ? 'text-brand-600' : ''}`}
                      />
                      {!sidebarCollapsed && (
                        <span className="truncate">{item.label}</span>
                      )}
                      {badgeCount > 0 && (
                        <span
                          className={`
                            flex-shrink-0 flex items-center justify-center min-w-[18px] h-[18px] px-1
                            text-[10px] font-bold rounded-full
                            ${isActive ? 'bg-brand-500 text-white' : 'bg-alert-500 text-white'}
                          `}
                        >
                          {badgeCount > 99 ? '99+' : badgeCount}
                        </span>
                      )}
                      {sidebarCollapsed && hoveredItem === item.id && (
                        <motion.div
                          initial={{ opacity: 0, x: -4 }}
                          animate={{ opacity: 1, x: 0 }}
                          className="absolute left-full ml-2 px-2 py-1 bg-finance-800 text-white text-xs rounded-md whitespace-nowrap z-50"
                        >
                          {item.label}
                        </motion.div>
                      )}
                    </motion.button>
                  );
                })}
              </div>
            </div>
          ))}
        </nav>

        <button
          onClick={toggleSidebar}
          className="flex items-center justify-center h-10 border-t border-surface-200/60 text-surface-400 hover:text-surface-600 hover:bg-surface-50 transition-colors"
        >
          {sidebarCollapsed ? <ChevronRight size={16} /> : <ChevronLeft size={16} />}
        </button>
      </motion.aside>

      <div className="flex-1 flex flex-col min-w-0 overflow-hidden">
        <header className="flex items-center justify-between h-14 px-5 border-b border-surface-200 bg-white z-10">
          <div>
            <h2 className="text-base font-semibold text-finance-800 font-display">
              {navSections
                .flatMap((s) => s.items)
                .find((i) => i.path === currentPath)?.label || '驾驶舱'}
            </h2>
          </div>

          <div className="flex items-center gap-3">
            <button
              className="relative p-2 rounded-xl text-surface-400 hover:text-surface-600 hover:bg-surface-100 transition-colors"
              onClick={() => navigate('/alert')}
            >
              <Bell size={18} />
              {totalBadgeCount > 0 && (
                <span className="absolute -top-0.5 -right-0.5 flex items-center justify-center min-w-[16px] h-[16px] px-0.5 text-[9px] font-bold bg-alert-500 text-white rounded-full">
                  {totalBadgeCount > 99 ? '99+' : totalBadgeCount}
                </span>
              )}
            </button>

            <div className="w-px h-6 bg-surface-200" />

            <div className="flex items-center gap-2 px-3 py-1.5 rounded-xl text-sm text-surface-600 hover:bg-surface-100 transition-colors">
              <div className="w-7 h-7 rounded-full bg-gradient-to-br from-brand-400 to-finance-600 flex items-center justify-center">
                <User size={14} className="text-white" />
              </div>
              <span className="font-medium">{user?.display_name || user?.username || '管理员'}</span>
            </div>

            <button
              onClick={() => { logout(); navigate('/login'); }}
              className="p-2 rounded-xl text-surface-400 hover:text-alert-600 hover:bg-alert-50 transition-colors"
              title="退出登录"
            >
              <LogOut size={18} />
            </button>
          </div>
        </header>

        <main className="flex-1 min-w-0 overflow-y-auto overflow-x-hidden p-6">
          <ProactiveInsightBanner />
          <Outlet />
        </main>

        <AIStatusBar />
      </div>

      <div className="fixed top-16 right-5 z-50 flex flex-col gap-2">
        <AnimatePresence>
          {toasts.map((toast) => (
            <motion.div
              key={toast.id}
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              transition={{ duration: 0.15 }}
              className={`
                flex items-start gap-3 px-3 py-2 rounded-lg border bg-white min-w-[260px] max-w-[360px]
                ${toast.type === 'success' ? 'border-compliance-200' : ''}
                ${toast.type === 'error' ? 'border-alert-200' : ''}
                ${toast.type === 'warning' ? 'border-warning-200' : ''}
                ${toast.type === 'info' ? 'border-brand-200' : ''}
              `}
            >
              <div className="flex-1">
                <p
                  className={`text-sm font-medium ${
                    toast.type === 'success' ? 'text-compliance-800' : ''
                  }${toast.type === 'error' ? 'text-alert-800' : ''}${
                    toast.type === 'warning' ? 'text-warning-800' : ''
                  }${toast.type === 'info' ? 'text-brand-800' : ''}`}
                >
                  {toast.title}
                </p>
                {toast.message && (
                  <p className="text-xs text-surface-500 mt-0.5">{toast.message}</p>
                )}
              </div>
              <button
                onClick={() => removeToast(toast.id)}
                className="text-surface-400 hover:text-surface-600 transition-colors"
              >
                <X size={14} />
              </button>
            </motion.div>
          ))}
        </AnimatePresence>
      </div>
    </div>
  );
}
