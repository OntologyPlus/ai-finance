import { useState, useEffect, useRef, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import { Search, X, ArrowRight } from 'lucide-react';

interface CommandAction {
  label: string;
  path: string;
  shortcut?: string;
}

const quickActions: CommandAction[] = [
  { label: '📊 生成月度报告', path: '/report' },
  { label: '💰 查看所有超支科目', path: '/budget' },
  { label: '🔔 处理待办预警', path: '/alert' },
  { label: '✅ 批量审批报销', path: '/approval' },
  { label: '📈 经营分析', path: '/analysis' },
  { label: '💬 与AI对话', path: '/ai-agent' },
];

export default function CommandPalette() {
  const navigate = useNavigate();
  const [isOpen, setIsOpen] = useState(false);
  const [inputValue, setInputValue] = useState('');
  const inputRef = useRef<HTMLInputElement>(null);
  const modalRef = useRef<HTMLDivElement>(null);

  const open = useCallback(() => {
    setIsOpen(true);
    setInputValue('');
  }, []);

  const close = useCallback(() => {
    setIsOpen(false);
    setInputValue('');
  }, []);

  // Ctrl/Cmd + K to open
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
        e.preventDefault();
        isOpen ? close() : open();
      }
      if (e.key === 'Escape' && isOpen) {
        close();
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isOpen, open, close]);

  // Focus input when opened
  useEffect(() => {
    if (isOpen) {
      setTimeout(() => inputRef.current?.focus(), 100);
    }
  }, [isOpen]);

  // Click outside to close
  const handleBackdropClick = (e: React.MouseEvent) => {
    if (modalRef.current && !modalRef.current.contains(e.target as Node)) {
      close();
    }
  };

  const handleAction = (path: string) => {
    close();
    navigate(path);
  };

  const handleNaturalLanguageSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (inputValue.trim()) {
      close();
      navigate(`/ai-agent?msg=${encodeURIComponent(inputValue.trim())}`);
    }
  };

  const filteredActions = quickActions.filter((a) =>
    a.label.toLowerCase().includes(inputValue.toLowerCase())
  );

  return (
    <AnimatePresence>
      {isOpen && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.15 }}
          className="fixed inset-0 z-[100] flex items-start justify-center pt-[20vh] bg-finance-900/40 backdrop-blur-sm"
          onClick={handleBackdropClick}
        >
          <motion.div
            ref={modalRef}
            initial={{ opacity: 0, scale: 0.96, y: -8 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.96, y: -8 }}
            transition={{ duration: 0.2, ease: 'easeOut' }}
            className="w-full max-w-lg rounded-2xl bg-white/95 backdrop-blur-xl shadow-2xl border border-surface-200/60 overflow-hidden"
          >
            {/* Header */}
            <div className="flex items-center gap-3 px-4 py-3 border-b border-surface-200/60">
              <Search size={18} className="text-surface-400 flex-shrink-0" />
              <input
                ref={inputRef}
                type="text"
                placeholder="输入指令或用自然语言描述..."
                className="flex-1 text-sm text-surface-700 placeholder:text-surface-400 bg-transparent outline-none"
                value={inputValue}
                onChange={(e) => setInputValue(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' && inputValue.trim()) {
                    handleNaturalLanguageSubmit(e);
                  }
                }}
              />
              <button
                onClick={close}
                className="p-1 rounded-lg text-surface-400 hover:text-surface-600 hover:bg-surface-100 transition-colors"
              >
                <X size={16} />
              </button>
            </div>

            {/* Quick Actions */}
            {filteredActions.length > 0 && (
              <div className="px-3 py-2 max-h-[40vh] overflow-y-auto">
                <p className="px-2 py-1.5 text-[10px] font-semibold uppercase tracking-widest text-surface-400">
                  快捷指令
                </p>
                <div className="space-y-0.5">
                  {filteredActions.map((action) => (
                    <motion.button
                      key={action.path}
                      onClick={() => handleAction(action.path)}
                      whileHover={{ x: 2, backgroundColor: 'rgba(241, 245, 249, 0.8)' }}
                      whileTap={{ scale: 0.98 }}
                      className="w-full flex items-center justify-between px-3 py-2.5 rounded-xl text-sm text-surface-600 hover:text-surface-800 transition-colors"
                    >
                      <span className="font-medium">{action.label}</span>
                      <ArrowRight size={14} className="text-surface-300" />
                    </motion.button>
                  ))}
                </div>
              </div>
            )}

            {/* Natural Language Footer */}
            {inputValue && (
              <motion.div
                initial={{ opacity: 0, height: 0 }}
                animate={{ opacity: 1, height: 'auto' }}
                exit={{ opacity: 0, height: 0 }}
                className="px-3 pb-3 border-t border-surface-200/60 pt-2"
              >
                <button
                  onClick={handleNaturalLanguageSubmit}
                  className="w-full flex items-center justify-center gap-2 px-4 py-2.5 rounded-xl bg-brand-500 text-white text-sm font-medium hover:bg-brand-600 transition-colors"
                >
                  <Search size={14} />
                  用 AI 搜索: "{inputValue}"
                </button>
              </motion.div>
            )}

            {/* Hint */}
            {!inputValue && (
              <div className="px-4 py-2 border-t border-surface-200/60">
                <p className="text-[11px] text-surface-400 text-center">
                  按 <kbd className="px-1.5 py-0.5 rounded bg-surface-100 text-surface-500 font-mono text-[10px]">Esc</kbd> 关闭
                </p>
              </div>
            )}
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
