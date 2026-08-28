import { useState, useEffect } from 'react';
import { dashboardApi } from '../../services/api';

const statusConfig = {
  online: {
    color: 'bg-compliance-500',
    textColor: 'text-compliance-700',
    // v10.0: 删除 animate-pulse-slow
  },
  degraded: {
    color: 'bg-warning-500',
    textColor: 'text-warning-700',
  },
  offline: {
    color: 'bg-alert-500',
    textColor: 'text-alert-700',
  },
};

export default function AIStatusBar() {
  const [status, setStatus] = useState<'online' | 'degraded' | 'offline'>('online');
  const [latency, setLatency] = useState<number | null>(null);

  useEffect(() => {
    const checkHealth = async () => {
      const start = Date.now();
      try {
        await dashboardApi.getOverview();
        const elapsed = Date.now() - start;
        setLatency(elapsed);
        setStatus(elapsed > 2000 ? 'degraded' : 'online');
      } catch {
        setStatus('degraded');
      }
    };

    checkHealth();
    const interval = setInterval(checkHealth, 120000); // every 2 minutes
    return () => clearInterval(interval);
  }, []);

  const config = statusConfig[status];

  return (
    <div className={`flex items-center gap-2 px-4 py-1.5 text-[11px] ${config.textColor} border-t border-surface-200 bg-white`}>
      <div className={`w-1.5 h-1.5 rounded-full ${config.color}`} />
      <span className="font-medium">AI 引擎{status === 'online' ? '就绪' : status === 'degraded' ? '响应慢' : '离线'}</span>
      <span className="text-surface-300">|</span>
      <span>10 个 Skill · 37 个工具</span>
      {latency !== null && (
        <>
          <span className="text-surface-300">|</span>
          <span>响应 {latency}ms</span>
        </>
      )}
    </div>
  );
}
