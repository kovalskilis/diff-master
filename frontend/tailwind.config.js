/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        // Apple-inspired colors
        apple: {
          gray: {
            50: '#f5f5f7',
            100: '#e8e8ed',
            200: '#d2d2d7',
            300: '#b4b4bb',
            400: '#86868b',
            500: '#6e6e73',
            600: '#515154',
            700: '#424245',
            800: '#2c2c2e',
            900: '#1d1d1f',
          },
          blue: {
            DEFAULT: '#0071e3',
            hover: '#0077ED',
            dark: '#004fa3',
          },
        },
      },
      fontFamily: {
        sans: [
          '-apple-system',
          'BlinkMacSystemFont',
          'Inter',
          'SF Pro Display',
          'Segoe UI',
          'sans-serif',
        ],
      },
      boxShadow: {
        'apple': '0 4px 6px rgba(0, 0, 0, 0.07), 0 12px 24px rgba(0, 0, 0, 0.05)',
        'apple-lg': '0 8px 16px rgba(0, 0, 0, 0.1), 0 24px 48px rgba(0, 0, 0, 0.08)',
      },
      animation: {
        'fade-in': 'fadeIn 0.3s ease-in-out',
        'slide-up': 'slideUp 0.4s ease-out',
        'slide-down': 'slideDown 0.4s ease-out',
      },
      keyframes: {
        fadeIn: {
          '0%': { opacity: '0' },
          '100%': { opacity: '1' },
        },
        slideUp: {
          '0%': { transform: 'translateY(20px)', opacity: '0' },
          '100%': { transform: 'translateY(0)', opacity: '1' },
        },
        slideDown: {
          '0%': { transform: 'translateY(-20px)', opacity: '0' },
          '100%': { transform: 'translateY(0)', opacity: '1' },
        },
      },
    },
  },
  plugins: [],
}

