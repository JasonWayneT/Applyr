/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        primary: {
          DEFAULT: '#D97757',
          dim: '#BC5D3F',
          container: '#FBE8DE',
        },
        secondary: {
          DEFAULT: '#0F766E',
          dim: '#115E59',
          container: '#CCFBF1',
        },
        tertiary: {
          DEFAULT: '#475569',
          container: '#E2E8F0',
        },
        surface: {
          DEFAULT: '#F8FAFC',
          dim: '#E2E8F0',
          bright: '#F8FAFC',
          container: {
            DEFAULT: '#ECEFF3',
            lowest: '#ffffff',
            low: '#F1F5F9',
            high: '#E2E8F0',
            highest: '#D6DEE6',
          },
          variant: '#E2E8F0',
          tint: '#D97757',
        },
        'on-surface': {
          DEFAULT: '#0F172A',
          variant: '#475569',
        },
        'on-primary': {
          DEFAULT: '#FFFFFF',
          container: '#7A3520',
        },
        'on-secondary': {
          DEFAULT: '#FFFFFF',
          container: '#134E4A',
        },
        outline: {
          DEFAULT: '#94A3B8',
          variant: '#E2E8F0',
        },
        error: {
          DEFAULT: '#DC2626',
          dim: '#B91C1C',
          container: '#FEE2E2',
        },
        'on-error': {
          DEFAULT: '#FFFFFF',
          container: '#7F1D1D',
        },
        'inverse-surface': '#0F172A',
        'inverse-on-surface': '#CBD5E1',
        'inverse-primary': '#F0A57C',
        background: '#F8FAFC',
        'on-background': '#0F172A',
        // Status chips
        'status-backlog': { bg: '#E2E8F0', text: '#334155' },
        'status-applied': { bg: '#CCFBF1', text: '#115E59' },
        'status-recruiter': { bg: '#ECEFF3', text: '#475569' },
        'status-core': { bg: '#DBEAFE', text: '#1E3A8A' },
        'status-offer': { bg: '#D1FAE5', text: '#065F46' },
        'status-closed': { bg: '#E2E8F0', text: '#475569' },
      },
      fontFamily: {
        headline: ['Manrope', 'sans-serif'],
        body: ['Inter', 'sans-serif'],
        sans: ['Inter', 'system-ui', 'sans-serif'],
      },
      borderRadius: {
        'sm': '0.25rem',
        'md': '0.75rem',
        'lg': '1rem',
        'xl': '1.5rem',
        '2xl': '2rem',
        '3xl': '2rem',
      },
    },
  },
  plugins: [],
}
