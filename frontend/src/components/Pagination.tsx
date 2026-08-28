import { clsx } from 'clsx';
import { ChevronLeft, ChevronRight } from 'lucide-react';

interface PaginationProps {
  currentPage: number;
  totalPages: number;
  onPageChange: (page: number) => void;
  pageSize?: number;
}

function getPageNumbers(current: number, total: number): (number | 'ellipsis')[] {
  if (total <= 7) {
    return Array.from({ length: total }, (_, i) => i + 1);
  }

  const pages: (number | 'ellipsis')[] = [];

  // Always show first page
  pages.push(1);

  if (current > 3) {
    pages.push('ellipsis');
  }

  // Show pages around current
  const start = Math.max(2, current - 1);
  const end = Math.min(total - 1, current + 1);

  for (let i = start; i <= end; i++) {
    pages.push(i);
  }

  if (current < total - 2) {
    pages.push('ellipsis');
  }

  // Always show last page
  if (total > 1) {
    pages.push(total);
  }

  return pages;
}

export default function Pagination({ currentPage, totalPages, onPageChange, pageSize }: PaginationProps) {
  if (totalPages <= 1) return null;

  const pages = getPageNumbers(currentPage, totalPages);

  return (
    <div className="flex items-center justify-between py-3 px-1">
      <div className="text-xs text-surface-400">
        第 {currentPage} / {totalPages} 页{pageSize ? ` · 每页 ${pageSize} 条` : ''}
      </div>
      <div className="flex items-center gap-1">
        <button
          onClick={() => onPageChange(currentPage - 1)}
          disabled={currentPage <= 1}
          className={clsx(
            'flex items-center justify-center w-8 h-8 rounded-lg text-sm transition-colors',
            currentPage <= 1
              ? 'text-surface-300 cursor-not-allowed'
              : 'text-surface-600 hover:bg-finance-50 hover:text-finance-700'
          )}
        >
          <ChevronLeft size={14} />
        </button>

        {pages.map((page, idx) =>
          page === 'ellipsis' ? (
            <span key={`ellipsis-${idx}`} className="w-8 h-8 flex items-center justify-center text-xs text-surface-400">
              ...
            </span>
          ) : (
            <button
              key={page}
              onClick={() => onPageChange(page)}
              className={clsx(
                'flex items-center justify-center w-8 h-8 rounded-lg text-sm font-medium transition-colors',
                page === currentPage
                  ? 'bg-finance-600 text-white shadow-sm'
                  : 'text-surface-600 hover:bg-finance-50 hover:text-finance-700'
              )}
            >
              {page}
            </button>
          )
        )}

        <button
          onClick={() => onPageChange(currentPage + 1)}
          disabled={currentPage >= totalPages}
          className={clsx(
            'flex items-center justify-center w-8 h-8 rounded-lg text-sm transition-colors',
            currentPage >= totalPages
              ? 'text-surface-300 cursor-not-allowed'
              : 'text-surface-600 hover:bg-finance-50 hover:text-finance-700'
          )}
        >
          <ChevronRight size={14} />
        </button>
      </div>
    </div>
  );
}
