/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx,ts,tsx}'],
  theme: {
    extend: {
      colors: {
        // Brand palette
        brand: {
          DEFAULT: '#6366f1',
          hover:   '#5558e8',
          muted:   '#818cf8',
        },
        // Surface palette (dark UI)
        surface: {
          DEFAULT:  '#0f1117',
          card:     '#1a1f2e',
          hover:    '#252d3d',
          border:   '#1e2535',
        },
      },
    },
  },
  plugins: [],
}
