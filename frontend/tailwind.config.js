/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        brand: {
          50: '#eff6ff',
          100: '#dbeafe',
          200: '#bfdbfe',
          300: '#93c5fd',
          400: '#60a5fa',
          500: '#3b82f6',
          600: '#2563eb',
          700: '#1d4ed8',
          800: '#1e40af',
          900: '#1e3a8a',
          950: '#172554',
        },
        finance: {
          50: '#eff6ff',
          100: '#dbeafe',
          200: '#bfdbfe',
          300: '#93c5fd',
          400: '#60a5fa',
          500: '#3b82f6',
          600: '#1d4ed8',
          700: '#1e3a8a',
          800: '#1e2d5e',
          900: '#0f1b3d',
          950: '#0a1128',
        },
        health: {
          50: '#f0fdf4',
          100: '#dcfce7',
          200: '#bbf7d0',
          300: '#86efac',
          400: '#4ade80',
          500: '#22c55e',
          600: '#16a34a',
          700: '#15803d',
          800: '#166534',
          900: '#14532d',
        },
        surface: {
          50: '#f8fafc',
          100: '#f1f5f9',
          200: '#e2e8f0',
          300: '#cbd5e1',
          400: '#94a3b8',
          500: '#64748b',
          600: '#475569',
          700: '#334155',
          800: '#1e293b',
          900: '#0f172a',
        },
        alert: {
          50: '#fef2f2',
          100: '#fee2e2',
          200: '#fecaca',
          300: '#fca5a5',
          400: '#f87171',
          // v12.2 视觉降噪：500/600/700 整体右移一档（更柔和）
          500: '#f87171',  // 原 400（柔和粉红）
          600: '#ef4444',  // 原 500
          700: '#dc2626',  // 原 600
          800: '#b91c1c',
          900: '#7f1d1d',
        },
        warning: {
          50: '#fffbeb',
          100: '#fef3c7',
          200: '#fde68a',
          300: '#fcd34d',
          400: '#fbbf24',
          // v12.2 视觉降噪：500/600/700 整体右移一档（更柔和）
          500: '#fbbf24',  // 原 400（柔和金黄）
          600: '#f59e0b',  // 原 500
          700: '#d97706',  // 原 600
          800: '#b45309',
          900: '#78350f',
        },
        compliance: {
          50: '#ecfdf5',
          100: '#d1fae5',
          200: '#a7f3d0',
          300: '#6ee7b7',
          400: '#34d399',
          500: '#10b981',
          600: '#059669',
          700: '#047857',
          800: '#065f46',
          900: '#064e3b',
        },
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', '-apple-system', 'sans-serif'],
        display: ['Outfit', 'Inter', 'system-ui', 'sans-serif'],
      },
      boxShadow: {
        finance: '0 1px 3px 0 rgba(30, 58, 138, 0.1), 0 1px 2px -1px rgba(30, 58, 138, 0.1)',
        'finance-lg': '0 10px 15px -3px rgba(30, 58, 138, 0.1), 0 4px 6px -4px rgba(30, 58, 138, 0.1)',
      },
      // v10.0: 删除 pulse-slow/float 动画（视觉降噪）
      animation: {},
      keyframes: {},
    },
  },
  plugins: [],
};
