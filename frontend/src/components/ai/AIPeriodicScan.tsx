import { useState, useEffect, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { dashboardApi } from '../../services/api';
import { useAppStore } from '../../store';
import { Bot, X, ArrowRight } from 'lucide-react';
import { useNavigate } from 'react-router-dom';

const SCAN_INTERVAL = 120000; // 2 minutes

interface PendingAlert {
  id: string;
  title: string;
  type: 'alert' | 'budget' | 'approval';
  path: string;
}

export default function AIPeriodicScan() {
  const addToast = useAppStore((s) => s.addToast);
  const [pendingAlert, setPendingAlert] = useState<PendingAlert | null>(null);
  const lastAlertRef = useRef<string>('');
  const navigate = useNavigate();

  useEffect(() => {
    const scan = async () => {
      try {
        const res = await dashboardApi.getOverview();
        const data = res.data;
        if (!data) return;

        // Check for new critical alerts
        const recentAlerts = data.recent_alerts || [];
        const activeAlerts = recentAlerts.filter((a: any) => a.status === 'active' && (a.alert_level === 'red' || a.alert_level === 'orange'));

        if (activeAlerts.length > 0) {
          const firstAlert = activeAlerts[0];
          if (firstAlert.alert_id !== lastAlertRef.current) {
            lastAlertRef.current = firstAlert.alert_id;
            setPendingAlert({
              id: firstAlert.alert_id,
              title: firstAlert.title,
              type: 'alert',
              path: '/alert',
            });
            addToast({
              type: 'warning',
              title: '🔍 AI 发现异常',
              message: firstAlert.title,
              duration: 8000,
            });
          }
        }

        // Check for budget over-run
        const budgetByQuadrant = data.budget_by_quadrant || [];
        for (const q of budgetByQuadrant) {
          if (q.total_budget > 0) {
            const rate = (q.actual_spend / q.total_budget) * 100;
            if (rate > 110) {
              const alertId = `budget-over-${q.quadrant}`;
              if (alertId !== lastAlertRef.current) {
                lastAlertRef.current = alertId;
                setPendingAlert({
                  id: alertId,
                  title: `${q.quadrant}象限预算超支 ${rate.toFixed(0)}%`,
                  type: 'budget',
                  path: '/budget',
                });
                addToast({
                  type: 'warning',
                  title: `⚠️ ${q.quadrant}象限预算超支`,
                  message: `执行率已达 ${rate.toFixed(0)}%，建议立即关注`,
                  duration: 6000,
                });
              }
              break;
            }
          }
        }

        // Check for pending approvals
        const pendingCount = data.pending_approvals || 0;
        if (pendingCount > 5) {
          const alertId = `pending-approvals-${pendingCount}`;
          if (alertId !== lastAlertRef.current) {
            lastAlertRef.current = alertId;
            setPendingAlert({
              id: alertId,
              title: `你有 ${pendingCount} 笔报销待审批`,
              type: 'approval',
              path: '/approval',
            });
          }
        }
      } catch {
        // Silently fail
      }
    };

    // Initial scan after 10 seconds
    const timer = setTimeout(scan, 10000);
    const interval = setInterval(scan, SCAN_INTERVAL);

    return () => {
      clearTimeout(timer);
      clearInterval(interval);
    };
  }, [addToast]);

  // Auto-dismiss after 30 seconds
  useEffect(() => {
    if (pendingAlert) {
      const timer = setTimeout(() => setPendingAlert(null), 30000);
      return () => clearTimeout(timer);
    }
  }, [pendingAlert]);

  return (
    <AnimatePresence>
      {pendingAlert && (
        <motion.div
          initial={{ opacity: 0, y: 20, scale: 0.9 }}
          animate={{ opacity: 1, y: 0, scale: 1 }}
          exit={{ opacity: 0, y: 20, scale: 0.9 }}
          transition={{ type: 'spring', stiffness: 400, damping: 25 }}
          className="fixed bottom-12 right-6 z-50"
        >
          <div className="relative">
            {/* Pulsing ring */}
            <motion.div
              animate={{ scale: [1, 1.3, 1], opacity: [0.6, 0, 0.6] }}
              transition={{ duration: 2, repeat: Infinity }}
              className="absolute inset-0 rounded-full bg-alert-500/30"
            />

            {/* Avatar */}
            <div className="relative flex items-center gap-3 p-3 rounded-2xl bg-white border border-alert-200 shadow-xl min-w-[260px]">
              <div className="flex-shrink-0 w-9 h-9 rounded-xl bg-gradient-to-br from-finance-500 to-finance-700 flex items-center justify-center">
                <Bot size={16} className="text-white" />
              </div>
              <div className="flex-1 min-w-0">
                <p className="text-xs font-semibold text-finance-800">AI 发现异常</p>
                <p className="text-[10px] text-surface-500 truncate">{pendingAlert.title}</p>
              </div>
              <button
                onClick={() => navigate(pendingAlert.path)}
                className="flex-shrink-0 p-1.5 rounded-lg bg-brand-50 text-brand-600 hover:bg-brand-100 transition-colors"
              >
                <ArrowRight size={14} />
              </button>
              <button
                onClick={() => setPendingAlert(null)}
                className="flex-shrink-0 p-1.5 rounded-lg text-surface-400 hover:text-surface-600 hover:bg-surface-100 transition-colors"
              >
                <X size={12} />
              </button>
            </div>
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
