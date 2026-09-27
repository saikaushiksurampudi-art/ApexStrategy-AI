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
        mono: ['ui-monospace', 'SFMono-Regular', 'Menlo', 'monospace'],
      },
      borderRadius: { xl: '0.875rem' },
    },
  },
  plugins: [],
}
