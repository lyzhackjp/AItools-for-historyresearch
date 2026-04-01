/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        primary: '#1890ff',
        secondary: '#52c41a',
        background: '#f0f2f5',
      },
      fontSize: {
        'senior-base': '18px',
        'senior-lg': '20px',
      },
    },
  },
  plugins: [],
  corePlugins: {
    preflight: false,
  },
}
