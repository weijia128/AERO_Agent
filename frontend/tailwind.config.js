/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        // 科技感暗色主题
        'bg-primary': '#0d1117',      // 深空黑
        'bg-card': '#161b22',         // 卡片背景
        'border': '#30363d',          // 边框
        'accent-green': '#238636',    // 科技绿
        'accent-blue': '#1f6feb',     // 科技蓝
        'warning': '#d29922',         // 琥珀黄
        'danger': '#f85149',          // 警报红
        'text-primary': '#e6edf3',    // 浅灰白
        'text-secondary': '#8b949e',  // 灰色
      },
      fontFamily: {
        mono: ['JetBrains Mono', 'Menlo', 'Monaco', 'Consolas', 'monospace'],
      },
      animation: {
        'pulse-glow': 'pulse-glow 2s ease-in-out infinite',
        'typing': 'typing 0.5s ease-in-out',
      },
      keyframes: {
        'pulse-glow': {
          '0%, 100%': { boxShadow: '0 0 5px rgba(35, 134, 54, 0.5)' },
          '50%': { boxShadow: '0 0 20px rgba(35, 134, 54, 0.8)' },
        },
      },
    },
  },
  plugins: [],
  darkMode: 'class',
}
