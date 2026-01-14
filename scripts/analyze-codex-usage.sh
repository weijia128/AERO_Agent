#!/bin/bash

# AERO_Agent Codex Usage Analysis Script
# This script analyzes Codex CLI usage from logs

echo "🔍 AERO_Agent Codex Usage Analysis"
echo "=================================="
echo ""

CODEX_LOG="$HOME/.codex/log/codex-tui.log"

if [ ! -f "$CODEX_LOG" ]; then
    echo "❌ Codex log file not found: $CODEX_LOG"
    exit 1
fi

echo "📁 Log file: $CODEX_LOG"
echo "📊 File size: $(du -h "$CODEX_LOG" | cut -f1)"
echo "📅 Total entries: $(wc -l < "$CODEX_LOG")"
echo ""

# Date range
echo "📅 Date Range"
echo "============="
echo "First entry: $(head -1 "$CODEX_LOG" | cut -d' ' -f1)"
echo "Last entry: $(tail -1 "$CODEX_LOG" | cut -d' ' -f1)"
echo ""

# Tool usage breakdown
echo "🔧 Tool Usage Breakdown"
echo "========================"
echo "Shell commands: $(grep -c "ToolCall.*shell_command" "$CODEX_LOG")"
echo "File reads: $(grep -c "ToolCall.*file_read" "$CODEX_LOG")"
echo "File writes: $(grep -c "ToolCall.*file_write" "$CODEX_LOG")"
echo "Multi edits: $(grep -c "ToolCall.*multi_edit_write" "$CODEX_LOG")"
echo "Grep searches: $(grep -c "ToolCall.*file_grep_search" "$CODEX_LOG")"
echo ""

# Working directory analysis
echo "📂 Working Directory Analysis"
echo "============================="
echo "Top directories:"
grep -o '"workdir":"[^"]*"' "$CODEX_LOG" | cut -d'"' -f4 | sort | uniq -c | sort -rn | head -10
echo ""

# Recent activity
echo "⏰ Recent Activity (Last 10 Commands)"
echo "====================================="
tail -100 "$CODEX_LOG" | grep "ToolCall" | tail -10 | while read line; do
    timestamp=$(echo "$line" | cut -d' ' -f1)
    command=$(echo "$line" | grep -o '"command":"[^"]*"' | cut -d'"' -f4 | head -c 50)
    echo "  $timestamp - $command"
done
echo ""

# Session analysis
echo "💬 Session Analysis"
echo "==================="
echo "Estimated sessions: $(grep -c "INFO.*session" "$CODEX_LOG")"
echo ""

# Error analysis
echo "⚠️ Error Analysis"
echo "=================="
error_count=$(grep -c "error\|Error\|ERROR" "$CODEX_LOG")
echo "Total errors: $error_count"

if [ $error_count -gt 0 ]; then
    echo "Recent errors:"
    tail -100 "$CODEX_LOG" | grep "error\|Error\|ERROR" | tail -5 | while read line; do
        echo "  $line"
    done
fi
echo ""

# Summary
echo "📈 Usage Summary"
echo "================"
total_tool_calls=$(grep -c "ToolCall" "$CODEX_LOG")
echo "Total tool calls: $total_tool_calls"
echo "Avg calls per day: $((total_tool_calls / 30))"
echo ""

echo "💡 Note: This analysis is based on Codex CLI logs."
echo "   Token usage and costs are not tracked in the logs."
echo "   For complete usage analysis, check:"
echo "   - OpenAI dashboard for API costs"
echo "   - Claude Code usage (separate from Codex)"
