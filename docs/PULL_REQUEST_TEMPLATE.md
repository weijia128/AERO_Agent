# Add Comprehensive Claude Code Monitoring and Usage Analysis Tools

## 📋 Summary

This PR introduces a complete monitoring ecosystem for Claude Code and Codex usage analysis, providing real-time monitoring, cost tracking, and comprehensive reporting capabilities.

## 🎯 Key Features

### 📊 Monitoring Tools
- **better-ccflare Integration**: Real-time Web dashboard with proxy support
- **ccusage CLI**: Command-line usage analysis with JSON export
- **claude-monitor**: Terminal-based real-time monitoring
- **Codex Analysis**: Log-based usage analysis for CLI tools

### 🔧 Utility Scripts
- **install-tools.sh**: One-click installation of all monitoring tools
- **usage-monitor.sh**: Comprehensive usage analysis (daily/monthly/session)
- **quick-check.sh**: System health check for all tools
- **weekly-report.sh**: Automated weekly usage reports
- **cleanup.sh**: System maintenance and cleanup
- **analyze-codex-usage.sh**: Codex CLI usage analysis

### 📁 New Files Added

#### Configuration Files
- `.claude/commands/check-usage.md` - Slash command documentation
- `.config/usage-monitors/config.toml` - Monitoring configuration

#### Scripts (9 total)
- `scripts/install-tools.sh` - Tool installer
- `scripts/setup-ccflare-env.sh` - Environment setup
- `scripts/start-proxy.sh` - Proxy launcher
- `scripts/start-ccflare-docker.sh` - Docker startup
- `scripts/usage-monitor.sh` - Usage monitoring
- `scripts/analyze-codex-usage.sh` - Codex analysis
- `scripts/quick-check.sh` - Health check
- `scripts/weekly-report.sh` - Report generator
- `scripts/cleanup.sh` - Maintenance tool

#### Documentation
- `docs/USAGE_MONITOR_GUIDE.md` - Complete usage guide
- `scripts/README.md` - Scripts documentation

## 🚀 Usage Examples

### Quick Start
```bash
# Install all tools
./scripts/install-tools.sh

# Start monitoring
./scripts/start-proxy.sh

# Check usage
npx ccusage daily --breakdown

# Real-time monitoring
claude-monitor --plan pro --view realtime
```

### Daily Monitoring
```bash
# Quick health check
./scripts/quick-check.sh

# Daily usage
npx ccusage daily --breakdown

# Web dashboard
open http://localhost:8080
```

### Weekly Analysis
```bash
# Generate comprehensive report
./scripts/weekly-report.sh

# View report
cat reports/weekly-summary-$(date +%Y%m%d).md
```

## 📊 Current Usage Statistics

### Claude Code
- Total Cost: $244.34 (44 days)
- Total Tokens: 688M+
- Daily Average: ~$5.55
- Cache Efficiency: 97.4% (excellent!)

### Codex CLI
- Active Period: 6 days (Jan 8-13)
- Tool Calls: 1,298 total
- Daily Average: 43 calls/day
- Main Activity: Code review and file operations

## 🎯 Benefits

### ✅ Cost Optimization
- Real-time cost tracking
- Usage pattern analysis
- Model distribution monitoring
- Cache efficiency insights

### ✅ Productivity Enhancement
- Automated report generation
- Health check automation
- Quick status overview
- Historical analysis

### ✅ Developer Experience
- Beautiful Web dashboard
- Terminal real-time monitoring
- Comprehensive CLI tools
- Complete documentation

## 🔗 Integration

### With awesome-claude-code Ecosystem
- Uses CC Usage (ryoppippi/ccusage)
- Uses claude-monitor (Maciek-roboblog)
- Uses better-ccflare (tombii/better-ccflare)
- Compatible with all Claude Code workflows

### Docker Integration
- Pre-configured Docker containers
- Easy deployment
- Resource management
- Health monitoring

## 📈 Testing

All scripts have been tested and verified:
- ✅ Tool installations successful
- ✅ Script execution tested
- ✅ Documentation validated
- ✅ Configuration files verified

## 🔄 Maintenance

Automated maintenance features:
- Old report cleanup (30+ days)
- Docker resource pruning
- Log rotation recommendations
- System health monitoring

## 📋 Files Changed

```
13 files added, 1,746 insertions(+)
```

## 🎯 Next Steps

After merging:
1. Run `./scripts/install-tools.sh` to set up tools
2. Start monitoring with `./scripts/start-proxy.sh`
3. Begin daily usage tracking with `npx ccusage daily`
4. Set up weekly reports with `./scripts/weekly-report.sh`

---

**Related Issues:** #2 (monitoring-tools)
**Type:** Enhancement
**Priority:** High
**Reviewer:** @weijia128

**Co-Authored-By:** Claude Sonnet 4.5 <noreply@anthropic.com>
