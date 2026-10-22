import type { Config } from 'tailwindcss';

export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        accent: { DEFAULT: '#4F46E5', soft: '#6366F1', strong: '#4338CA' },
      },
      borderRadius: { card: '16px' },
      fontFamily: {
        sans: ['"Inter Variable"', 'Inter', 'ui-sans-serif', 'system-ui', 'sans-serif'],
      },
      boxShadow: {
        float: '0 1px 2px rgba(15,23,42,0.04), 0 12px 32px -8px rgba(15,23,42,0.18)',
        card: '0 1px 2px rgba(15,23,42,0.05), 0 4px 12px -4px rgba(15,23,42,0.08)',
        glow: '0 8px 24px -6px rgba(79,70,229,0.45)',
      },
    },
  },
  plugins: [],
} satisfies Config;
