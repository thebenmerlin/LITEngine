/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        navy: {
          50: '#F0F2F7',
          100: '#E1E5EF',
          200: '#C3CBDE',
          300: '#A5B1CD',
          400: '#8797BC',
          500: '#697DAB',
          600: '#4B639A',
          700: '#1B2A4A',
          800: '#152139',
          900: '#0F1828',
        },
        surface: {
          light: '#FFFFFF',
          dark: '#0F1117',
        },
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', '-apple-system', 'sans-serif'],
      },
    },
  },
  plugins: [],
}
