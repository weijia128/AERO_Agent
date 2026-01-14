#!/bin/bash

# AERO_Agent Quick Health Check
# This script provides a quick overview of all monitoring tools

echo "🔍 AERO_Agent Monitoring Tools - Quick Check"
echo "============================================"
echo ""

# 1. Check better-ccflare
echo "1️⃣ better-ccflare Status"
echo "========================="
if docker ps | grep -q better-ccflare; then
    echo "✅ Running"
    echo "   🌐 Dashboard: http://localhost:8080"
    echo "   📊 Status: $(curl -s http://localhost:8080/health | jq -r '.status' 2>/dev/null || echo 'unknown')"
else
    echo "❌ Not running"
    echo "   Start with: ./scripts/start-proxy.sh"
fi
echo ""

# 2. Check ccusage
echo "2️⃣ ccusage Availability"
echo "========================="
if command -v npx &> /dev/null; then
    echo "✅ npx available (ccusage ready)"
    echo "   Try: npx ccusage daily"
else
    echo "❌ npx not found"
fi
echo ""

# 3. Check claude-monitor
echo "3️⃣ claude-monitor Status"
echo "=========================="
if command -v claude-monitor &> /dev/null; then
    echo "✅ Installed"
    echo "   Try: claude-monitor --plan pro --view realtime"
else
    echo "❌ Not installed"
    echo "   Install with: uv tool install claude-monitor"
fi
echo ""

# 4. Check Codex logs
echo "4️⃣ Codex Usage Analysis"
echo "========================"
if [ -f "$HOME/.codex/log/codex-tui.log" ]; then
    echo "✅ Log file found"
    echo "   📄 Size: $(du -h "$HOME/.codex/log/codex-tui.log" | cut -f1)"
    echo "   📊 Entries: $(wc -l < "$HOME/.codex/log/codex-tui.log")"
    echo "   Run: ./scripts/analyze-codex-usage.sh"
else
    echo "❌ No Codex logs found"
fi
echo ""

# 5. Claude Code usage summary
echo "5️⃣ Claude Code Usage (Last 7 Days)"
echo "====================================="
if command -v npx &> /dev/null; then
    echo "📊 Generating summary..."
    npx ccusage daily --since $(date -d "7 days ago" +%Y%m%d) --compact 2>/dev/null | tail -10
else
    echo "❌ ccusage not available"
fi
echo ""

# 6. Summary and next steps
echo "6️⃣ Quick Actions"
echo "================="
echo "┌──────────────────────────────────────────────┐"
echo "│ View daily usage:                             │"
echo "│   npx ccusage daily --breakdown             │"
echo "│                                              │"
echo "│ Start real-time monitor:                      │"
echo "│   claude-monitor --plan pro                 │"
echo "│                                              │"
echo "│ Open web dashboard:                           │"
echo "│   open http://localhost:8080                 │"
echo "│                                              │"
echo "│ Run comprehensive analysis:                   │"
echo "│   ./scripts/usage-monitor.sh monthly         │"
echo "└──────────────────────────────────────────────┘"
echo ""

# 7. System info
echo "7️⃣ System Information"
echo "======================"
echo "🖥️  OS: $(uname -s)"
echo "🐳 Docker: $(docker --version 2>/dev/null || echo 'Not available')"
echo "📦 Node: $(node --version 2>/dev/null || echo 'Not available')"
echo "🐍 Python: $(python3 --version 2>/dev/null || echo 'Not available')"
echo "⚡ UV: $(uv --version 2>/dev/null || echo 'Not available')"
echo ""

echo "✅ Health check complete!"
