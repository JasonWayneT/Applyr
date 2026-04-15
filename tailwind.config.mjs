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
          DEFAULT: '#526452',
          dim: '#465746',
          container: '#d4e8d1',
        },
        secondary: {
          DEFAULT: '#8b4f3a',
          dim: '#7d4330',
          container: '#ffdbd0',
        },
        tertiary: {
          DEFAULT: '#605f5a',
          container: '#fdffda',
        },
        surface: {
          DEFAULT: '#faf9f6',
          dim: '#d9dbd6',
          bright: '#faf9f6',
          container: {
            DEFAULT: '#eeeeea',
            lowest: '#ffffff',
            low: '#f4f4f0',
            high: '#e8e9e4',
            highest: '#e1e3de',
          },
          variant: '#e1e3de',
          tint: '#526452',
        },
        'on-surface': {
          DEFAULT: '#303330',
          variant: '#5d605c',
        },
        'on-primary': {
          DEFAULT: '#ebfee7',
          container: '#455645',
        },
        'on-secondary': {
          DEFAULT: '#fff7f5',
          container: '#7c422e',
        },
        outline: {
          DEFAULT: '#797b78',
          variant: '#b0b3ae',
        },
        error: {
          DEFAULT: '#a73b21',
          dim: '#791903',
          container: '#fd795a',
        },
        'on-error': {
          DEFAULT: '#fff7f6',
          container: '#6e1400',
        },
        'inverse-surface': '#0d0f0d',
        'inverse-on-surface': '#9d9d9a',
        'inverse-primary': '#ebffe7',
        background: '#faf9f6',
        'on-background': '#303330',
        // Status chips
        'status-backlog': { bg: '#e1e3de', text: '#5d605c' },
        'status-applied': { bg: '#d4e8d1', text: '#455645' },
        'status-recruiter': { bg: '#eeeeea', text: '#5d605c' },
        'status-core': { bg: '#ffdbd0', text: '#7c422e' },
        'status-offer': { bg: '#d4e8d1', text: '#334333' },
        'status-closed': { bg: '#e1e3de', text: '#5d605c' },
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
