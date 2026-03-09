/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      colors: {
        surface: {
          DEFAULT: '#0f1117',
          card: '#1a1f2e',
          border: '#1e2535',
          hover: '#252d3d',
        },
        brand: {
          DEFAULT: '#6366f1',
          hover: '#5558e8',
          muted: '#818cf8',
        },
      },
    },
  },
  plugins: [],
}
