import type { Config } from 'tailwindcss';

const config: Config = {
  darkMode: 'class',
  content: ['./app/**/*.{js,ts,jsx,tsx,mdx}', './components/**/*.{js,ts,jsx,tsx,mdx}'],
  theme: {
    extend: {
      colors: {
        ink: '#0f1b2d',
        mist: '#f7f8fb',
        gold: '#2563eb',
        brand: {
          DEFAULT: '#2563eb',
          blue: '#2563eb',
          dark: '#1d4ed8',
          navy: '#12294d',
          deep: '#0a1730',
          soft: '#eef4ff',
        },
      },
      fontFamily: {
        sans: ['var(--font-cairo)', 'Tahoma', 'Arial', 'sans-serif'],
      },
      boxShadow: {
        soft: '0 18px 50px rgba(15, 23, 42, 0.08)',
      },
    },
  },
  plugins: [],
};

export default config;
