#!/bin/bash

# AERO_Agent Claude Code Usage Monitor Script
# Usage: ./scripts/usage-monitor.sh [daily|monthly|session|realtime]

VIEW=${1:-daily}
PROJECT_NAME="AERO_Agent"

echo "🎯 AERO_Agent Claude Code Usage Analysis"
echo "========================================="
echo "📅 View: $VIEW"
echo "📂 Project: $PROJECT_NAME"
echo "⏰ Timestamp: $(date)"
echo ""

case $VIEW in
    "daily")
        echo "📊 Daily Usage Report"
        echo "==================="
        npx ccusage daily --project "$PROJECT_NAME" --breakdown
        ;;
    "monthly")
        echo "📈 Monthly Usage Report"
        echo "====================="
        npx ccusage monthly --project "$PROJECT_NAME" --breakdown
        ;;
    "session")
        echo "💬 Session Analysis"
        echo "=================="
        npx ccusage session --project "$PROJECT_NAME" --since 20260101
        ;;
    "realtime")
        echo "⚡ Real-time Monitoring"
        echo "====================="
        echo "Starting Claude Code Usage Monitor..."
        if command -v claude-monitor &> /dev/null; then
            claude-monitor --plan pro --view realtime --theme dark
        else
            echo "❌ claude-monitor not installed"
            echo "Install with: uv tool install claude-monitor"
        fi
        ;;
    "cost")
        echo "💰 Cost Breakdown"
        echo "================="
        npx ccusage monthly --breakdown --json > usage-cost-$(date +%Y%m%d).json
        echo "📄 Cost report saved to: usage-cost-$(date +%Y%m%d).json"
        ;;
    "export")
        echo "📤 Exporting Usage Data"
        echo "====================="
        DATE=$(date +%Y%m%d)
        npx ccusage monthly --since 20260101 --json > "aero-agent-usage-${DATE}.json"
        echo "📄 Full usage data exported to: aero-agent-usage-${DATE}.json"
        ;;
    *)
        echo "❌ Unknown view: $VIEW"
        echo ""
        echo "Available views:"
        echo "  daily    - Daily usage report"
        echo "  monthly  - Monthly usage report"
        echo "  session  - Session analysis"
        echo "  realtime - Real-time monitoring (requires claude-monitor)"
        echo "  cost     - Cost breakdown export"
        echo "  export   - Full data export"
        exit 1
        ;;
esac

echo ""
echo "✅ Analysis complete!"
echo ""
echo "💡 Tips:"
echo "  - Use --json for machine-readable output"
echo "  - Check .claude/commands/check-usage.md for more options"
echo "  - Install real-time monitor: uv tool install claude-monitor"
