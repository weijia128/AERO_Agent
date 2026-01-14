#!/bin/bash

# AERO_Agent Cleanup and Maintenance Script
# This script cleans up logs, temporary files, and Docker resources

echo "🧹 AERO_Agent Cleanup and Maintenance"
echo "======================================"
echo ""

# Color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

print_status() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

print_header() {
    echo -e "\n${BLUE}=== $1 ===${NC}\n"
}

# Function to check if Docker is available
check_docker() {
    if ! command -v docker &> /dev/null; then
        print_error "Docker not found. Skipping Docker operations."
        return 1
    fi

    if ! docker ps &> /dev/null; then
        print_warning "Docker is not running. Skipping Docker operations."
        return 1
    fi

    return 0
}

# 1. Cleanup old reports
print_header "Cleaning Up Old Reports"
if [ -d "reports" ]; then
    # Keep only last 30 days of reports
    find reports/ -name "*.txt" -mtime +30 -delete 2>/dev/null
    find reports/ -name "*.json" -mtime +30 -delete 2>/dev/null
    find reports/ -name "*.md" -mtime +30 -delete 2>/dev/null
    print_status "Cleaned up reports older than 30 days"

    # Count remaining reports
    REPORT_COUNT=$(find reports/ -type f 2>/dev/null | wc -l)
    print_status "Remaining reports: $REPORT_COUNT files"
else
    print_status "No reports directory found"
fi

# 2. Cleanup temporary usage files
print_header "Cleaning Up Temporary Usage Files"
if ls usage-cost-*.json &> /dev/null; then
    rm -f usage-cost-*.json
    print_status "Removed temporary cost files"
else
    print_status "No temporary cost files found"
fi

if ls aero-agent-usage-*.json &> /dev/null; then
    rm -f aero-agent-usage-*.json
    print_status "Removed temporary usage export files"
else
    print_status "No temporary export files found"
fi

# 3. Cleanup Docker resources
print_header "Docker Resource Cleanup"

if check_docker; then
    # Remove stopped containers
    STOPPED_CONTAINERS=$(docker ps -aq --filter "status=exited" --filter "status=dead" | wc -l)
    if [ $STOPPED_CONTAINERS -gt 0 ]; then
        docker container prune -f
        print_status "Cleaned up $STOPPED_CONTAINERS stopped containers"
    else
        print_status "No stopped containers to clean"
    fi

    # Remove unused images
    UNUSED_IMAGES=$(docker images -q --filter "dangling=true" | wc -l)
    if [ $UNUSED_IMAGES -gt 0 ]; then
        docker image prune -f
        print_status "Cleaned up unused Docker images"
    else
        print_status "No unused images to clean"
    fi

    # Remove unused volumes
    UNUSED_VOLUMES=$(docker volume ls -q --filter "dangling=true" | wc -l)
    if [ $UNUSED_VOLUMES -gt 0 ]; then
        docker volume prune -f
        print_status "Cleaned up unused Docker volumes"
    else
        print_status "No unused volumes to clean"
    fi

    # Check better-ccflare container
    if docker ps -a | grep -q better-ccflare; then
        if docker ps | grep -q better-ccflare; then
            print_status "✅ better-ccflare container is running"
        else
            print_status "⚠️  better-ccflare container exists but is stopped"
            print_status "   To remove: docker rm better-ccflare"
            print_status "   To start: ./scripts/start-proxy.sh"
        fi
    fi
fi

# 4. Cleanup system logs (limited)
print_header "System Log Analysis"

# Check Codex logs
if [ -f "$HOME/.codex/log/codex-tui.log" ]; then
    LOG_SIZE=$(du -h "$HOME/.codex/log/codex-tui.log" | cut -f1)
    LOG_LINES=$(wc -l < "$HOME/.codex/log/codex-tui.log")
    print_status "Codex log size: $LOG_SIZE ($LOG_LINES lines)"

    # Check if log is larger than 100MB
    LOG_SIZE_BYTES=$(stat -f%z "$HOME/.codex/log/codex-tui.log" 2>/dev/null || stat -c%s "$HOME/.codex/log/codex-tui.log" 2>/dev/null)
    if [ "$LOG_SIZE_BYTES" -gt 104857600 ]; then
        print_warning "Codex log is larger than 100MB"
        print_status "   Consider archiving or rotating the log file"
        print_status "   Current size: $LOG_SIZE"
    fi
fi

# 5. Check disk usage
print_header "Disk Usage Summary"

# Project directory
if [ -d "." ]; then
    DISK_USAGE=$(du -sh . 2>/dev/null | cut -f1)
    print_status "Project directory: $DISK_USAGE"
fi

# Reports directory
if [ -d "reports" ]; then
    REPORTS_SIZE=$(du -sh reports 2>/dev/null | cut -f1)
    print_status "Reports directory: $REPORTS_SIZE"
fi

# 6. Generate maintenance report
print_header "Maintenance Report"

REPORT_FILE="reports/maintenance-$(date +%Y%m%d_%H%M).md"
mkdir -p reports

cat > "$REPORT_FILE" << EOF
# AERO_Agent Maintenance Report

**Generated:** $(date)

## 🧹 Cleanup Actions Performed

### Reports
- Removed reports older than 30 days
- Kept recent reports for analysis

### Temporary Files
- Removed temporary cost files
- Removed temporary usage export files

### Docker Resources
- Cleaned up stopped containers
- Removed unused images
- Removed unused volumes

### System Status

#### better-ccflare
$(if check_docker; then
    if docker ps | grep -q better-ccflare; then
        echo "✅ Running"
    else
        echo "⚠️  Stopped or not found"
    fi
else
    echo "❓ Docker not available"
fi)

#### Claude Code Usage
- Latest daily report: \`npx ccusage daily\`
- Latest monthly report: \`npx ccusage monthly\`

#### Codex Usage
- Log file: $HOME/.codex/log/codex-tui.log
- Size: $(du -h "$HOME/.codex/log/codex-tui.log" 2>/dev/null | cut -f1)
- Lines: $(wc -l < "$HOME/.codex/log/codex-tui.log" 2>/dev/null)

## 📊 Recommendations

1. **Regular Monitoring**
   - Run weekly reports: \`./scripts/weekly-report.sh\`
   - Check daily usage: \`npx ccusage daily\`

2. **Log Management**
   - Consider log rotation for large files
   - Archive old Codex logs periodically

3. **Docker Maintenance**
   - Run this cleanup script monthly
   - Monitor Docker disk usage

## 🔗 Quick Links

- Web Dashboard: http://localhost:8080
- Daily Usage: \`npx ccusage daily\`
- Quick Check: \`./scripts/quick-check.sh\`

---
*Generated by AERO_Agent Cleanup Script*
EOF

print_status "Maintenance report saved: $REPORT_FILE"

# 7. Display summary
print_header "Cleanup Summary"
echo "✅ Cleanup completed successfully!"
echo ""
echo "📋 Summary:"
echo "   - Reports: Cleaned (30+ days old removed)"
echo "   - Temporary files: Removed"
echo "   - Docker: Resources cleaned"
echo "   - Logs: Analyzed"
echo ""
echo "📄 Maintenance report: $REPORT_FILE"
echo ""
echo "💡 Next actions:"
echo "   1. Review the maintenance report"
echo "   2. Check Docker resources if needed"
echo "   3. Consider log rotation for large files"
echo ""
echo "🔄 To run this cleanup monthly:"
echo "   crontab -e"
echo "   Add: 0 2 1 * * /path/to/scripts/cleanup.sh"
