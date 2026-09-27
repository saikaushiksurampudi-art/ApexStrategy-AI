/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        // Surfaces: a single, deliberately selected dark theme. F1 team
        // colours are designed for dark backgrounds and every one of them
        // clears 3:1 contrast against surface-1 (verified, see docs/DESIGN.md).
        surface: {
          0: '#0e0f14',
          1: '#15161c',
          2: '#1c1e26',
          3: '#252833',
        },
        ink: {
          primary: '#f4f5f7',
          secondary: '#a8adba',
          muted: '#6f7686',
        },
        line: {
          DEFAULT: '#2a2e3a',
          strong: '#3a3f4f',
        },
        // Validated categorical slots (dark steps) for non-team series.
        series: {
          1: '#3987e5',
          2: '#d95926',
          3: '#199e70',
          4: '#c98500',
          5: '#d55181',
        },
        status: {
          good: '#199e70',
          warn: '#c98500',
          bad: '#e66767',
        },
        accent: '#e8002d',
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', '-apple-system', 'Segoe UI', 'sans-serif'],
        display: ['Archivo', 'Inter', 'system-ui', 'sans-serif'],
        mono: ['ui-monospace', 'SFMono-Regular', 'Menlo', 'monospace'],
      },
      borderRadius: { xl: '0.875rem', '2xl': '1.25rem' },
      keyframes: {
        'fade-up': {
          '0%': { opacity: '0', transform: 'translateY(14px)' },
          '100%': { opacity: '1', transform: 'none' },
        },
        'speed-sweep': {
          '0%': { transform: 'translateX(-120%)' },
          '100%': { transform: 'translateX(320%)' },
        },
        'slow-drift': {
          '0%, 100%': { transform: 'translate3d(0,0,0) scale(1)' },
          '50%': { transform: 'translate3d(2%, -3%, 0) scale(1.06)' },
        },
        'pulse-ring': {
          '0%': { opacity: '0.55', transform: 'scale(0.9)' },
          '70%, 100%': { opacity: '0', transform: 'scale(1.7)' },
        },
      },
      animation: {
        'fade-up': 'fade-up 620ms cubic-bezier(.22,.61,.36,1) both',
        'speed-sweep': 'speed-sweep 3.6s ease-in-out infinite',
        'slow-drift': 'slow-drift 18s ease-in-out infinite',
        'pulse-ring': 'pulse-ring 2.4s ease-out infinite',
      },
    },
  },
  plugins: [],
}
