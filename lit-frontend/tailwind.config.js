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
      keyframes: {
        'ping-slow': {
          '0%': { transform: 'scale(1)', opacity: '0.5' },
          '75%, 100%': { transform: 'scale(1.9)', opacity: '0' },
        },
        'fade-in-up': {
          '0%': { opacity: '0', transform: 'translateY(6px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
      },
      animation: {
        'ping-slow': 'ping-slow 2.5s cubic-bezier(0, 0, 0.2, 1) infinite',
        'fade-in-up': 'fade-in-up 0.2s ease-out',
      },
    },
  },
  plugins: [],
}
