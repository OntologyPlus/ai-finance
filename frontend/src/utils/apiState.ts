/**
 * apiState — 4 态封装工具（v9.0 C.6）
 *
 * 4 态：
 *   - loading: 请求进行中
 *   - error: 请求失败
 *   - empty: 请求成功但无数据
 *   - data: 请求成功且有数据
 *
 * 用法：
 *   const state = useApiState(async () => { ... });
 *   if (state.loading) return <Spinner />;
 *   if (state.error) return <ErrorView onRetry={state.retry} />;
 *   if (state.isEmpty) return <EmptyView />;
 *   return <DataView data={state.data} />;
 */
import { useState, useEffect, useCallback, useRef } from 'react';

export type ApiState<T> = {
  data: T | null;
  loading: boolean;
  error: string | null;
  isEmpty: boolean;
  retry: () => void;
};

export function useApiState<T>(
  fetcher: () => Promise<T>,
  deps: ReadonlyArray<unknown> = [],
  options: {
    isEmptyCheck?: (data: T | null) => boolean;
    initialData?: T | null;
  } = {},
): ApiState<T> {
  const [data, setData] = useState<T | null>(options.initialData ?? null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const fetcherRef = useRef(fetcher);

  // 保持 fetcher 引用最新
  fetcherRef.current = fetcher;

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const result = await fetcherRef.current();
      setData(result);
    } catch (e: any) {
      setError(e?.message || '请求失败');
      setData(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);

  const isEmptyCheck = options.isEmptyCheck ?? ((d: T | null) => {
    if (d == null) return true;
    if (Array.isArray(d)) return d.length === 0;
    if (typeof d === 'object') {
      // 处理 { data: [...], ... } 结构
      const arr = (d as any).data;
      if (Array.isArray(arr)) return arr.length === 0;
      return Object.keys(d as object).length === 0;
    }
    return false;
  });

  return {
    data,
    loading,
    error,
    isEmpty: isEmptyCheck(data),
    retry: load,
  };
}

// ── UI 组件：4 态统一展示 ─────────────────────────────────

import { Loader2, AlertCircle, Inbox, RefreshCw } from 'lucide-react';

export function StateLoading({ label = '加载中...' }: { label?: string }) {
  return (
    <div className="flex flex-col items-center justify-center py-10 text-surface-400 text-sm">
      <Loader2 className="w-5 h-5 animate-spin text-finance-500 mb-2" />
      {label}
    </div>
  );
}

export function StateError({ error, onRetry }: { error: string; onRetry?: () => void }) {
  return (
    <div className="flex flex-col items-center justify-center py-10 text-surface-500 text-sm">
      <AlertCircle className="w-6 h-6 text-alert-500 mb-2" />
      <p className="text-alert-700 font-medium">加载失败</p>
      <p className="text-[11px] text-surface-400 mt-1 max-w-md text-center">{error}</p>
      {onRetry && (
        <button
          onClick={onRetry}
          className="mt-3 text-xs px-3 py-1.5 rounded-lg bg-finance-50 hover:bg-finance-100 text-finance-700 border border-finance-200 flex items-center gap-1.5"
        >
          <RefreshCw size={12} /> 重试
        </button>
      )}
    </div>
  );
}

export function StateEmpty({ message = '暂无数据', hint }: { message?: string; hint?: string }) {
  return (
    <div className="flex flex-col items-center justify-center py-10 text-surface-400 text-sm">
      <Inbox className="w-6 h-6 opacity-50 mb-2" />
      <p className="text-surface-600 font-medium">{message}</p>
      {hint && <p className="text-[11px] text-surface-400 mt-1 max-w-md text-center">{hint}</p>}
    </div>
  );
}

export function StateView<T>({
  state,
  loadingLabel,
  emptyMessage,
  emptyHint,
  children,
}: {
  state: ApiState<T>;
  loadingLabel?: string;
  emptyMessage?: string;
  emptyHint?: string;
  children: (data: T) => React.ReactNode;
}) {
  if (state.loading) return <StateLoading label={loadingLabel} />;
  if (state.error) return <StateError error={state.error} onRetry={state.retry} />;
  if (state.isEmpty) return <StateEmpty message={emptyMessage} hint={emptyHint} />;
  return <>{children(state.data as T)}</>;
}
