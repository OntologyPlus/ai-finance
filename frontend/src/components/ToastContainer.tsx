import { motion, AnimatePresence } from 'framer-motion';
import { X, CheckCircle2, AlertCircle, AlertTriangle, Info } from 'lucide-react';
import { useAppStore } from '../store';

const TYPE_STYLES: Record<string, { bg: string; border: string; text: string; icon: typeof CheckCircle2 }> = {
  success: { bg: 'bg-compliance-50', border: 'border-compliance-200', text: 'text-compliance-700', icon: CheckCircle2 },
  error: { bg: 'bg-alert-50', border: 'border-alert-200', text: 'text-alert-700', icon: AlertCircle },
  warning: { bg: 'bg-warning-50', border: 'border-warning-200', text: 'text-warning-700', icon: AlertTriangle },
  info: { bg: 'bg-brand-50', border: 'border-brand-200', text: 'text-brand-700', icon: Info },
};

export default function ToastContainer() {
  const toasts = useAppStore((s) => s.toasts);
  const removeToast = useAppStore((s) => s.removeToast);

  return (
    <div className="fixed top-4 right-4 z-[100] flex flex-col gap-2 pointer-events-none" style={{ maxWidth: 380 }}>
      <AnimatePresence>
        {toasts.map((toast) => {
          const style = TYPE_STYLES[toast.type] || TYPE_STYLES.info;
          const Icon = style.icon;
          return (
            <motion.div
              key={toast.id}
              initial={{ opacity: 0, x: 60, scale: 0.95 }}
              animate={{ opacity: 1, x: 0, scale: 1 }}
              exit={{ opacity: 0, x: 60, scale: 0.95 }}
              transition={{ duration: 0.2 }}
              onClick={() => removeToast(toast.id)}
              className={`pointer-events-auto flex items-start gap-3 px-4 py-3 rounded-xl border shadow-lg cursor-pointer ${style.bg} ${style.border}`}
            >
              <Icon size={18} className={`${style.text} flex-shrink-0 mt-0.5`} />
              <div className="flex-1 min-w-0">
                <p className={`text-sm font-medium ${style.text}`}>{toast.title}</p>
                {toast.message && (
                  <p className="text-xs text-surface-500 mt-0.5">{toast.message}</p>
                )}
              </div>
              <button
                onClick={(e) => { e.stopPropagation(); removeToast(toast.id); }}
                className="text-surface-400 hover:text-surface-600 flex-shrink-0"
              >
                <X size={14} />
              </button>
            </motion.div>
          );
        })}
      </AnimatePresence>
    </div>
  );
}
