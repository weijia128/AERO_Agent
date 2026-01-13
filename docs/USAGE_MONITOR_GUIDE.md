# AERO_Agent Claude Code Usage Monitor Guide

This guide explains how to monitor and analyze your Claude Code usage for the AERO_Agent project using the awesome-claude-code ecosystem tools.

## 📦 Quick Setup

### Option 1: Lightweight Analysis (Recommended for Starters)

```bash
# Install ccusage (no global install needed)
npx ccusage@latest daily

# Or use our convenience script
./scripts/usage-monitor.sh daily
```

### Option 2: Real-time Monitoring

```bash
# Install claude-monitor
uv tool install claude-monitor

# Run with our config
claude-monitor --config .config/usage-monitors/config.toml

# Or use our script
./scripts/usage-monitor.sh realtime
```

### Option 3: Web Dashboard with Proxy

```bash
# Start the proxy (installed globally)
./scripts/start-proxy.sh

# Then configure Claude Code:
export ANTHROPIC_BASE_URL=http://localhost:8080

# Access dashboard at http://localhost:8080
```

## 🚀 Quick Start Commands

### Daily Usage Check
```bash
# Simple daily report
npx ccusage daily

# Detailed breakdown
npx ccusage daily --breakdown

# Filter by project
npx ccusage daily --project AERO_Agent
```

### Monthly Analysis
```bash
# Monthly summary
npx ccusage monthly

# With cost breakdown
npx ccusage monthly --breakdown

# JSON export for analysis
npx ccusage monthly --json > aero-usage.json
```

### Session Analysis
```bash
# View recent sessions
npx ccusage session

# Sessions with breakdown
npx ccusage session --breakdown

# Filter by date range
npx ccusage session --since 20260101
```

### Cost Analysis
```bash
# Generate cost report
./scripts/usage-monitor.sh cost

# This creates: usage-cost-YYYYMMDD.json
```

## 📊 Using the Scripts

### Usage Monitor Script
```bash
# Available views
./scripts/usage-monitor.sh daily      # Daily usage
./scripts/usage-monitor.sh monthly   # Monthly usage
./scripts/usage-monitor.sh session   # Session analysis
./scripts/usage-monitor.sh realtime   # Real-time monitor
./scripts/usage-monitor.sh cost      # Cost breakdown
./scripts/usage-monitor.sh export    # Full data export
```

### Proxy Setup Script
```bash
# Interactive proxy setup
./scripts/start-proxy.sh

# Manual start
better-ccflare &
export ANTHROPIC_BASE_URL=http://localhost:8080
```

## 🎯 Integration with Claude Code

### 1. Command Integration

Use the `/check-usage` slash command in Claude Code:

```
/check-usage daily
/check-usage monthly
/check-usage session
```

### 2. Hook Integration

Add usage monitoring to your hooks:

```json
{
  "hooks": {
    "post_tool_use": [
      {
        "command": "npx ccusage daily --compact"
      }
    ]
  }
}
```

### 3. Environment Configuration

Add to your `.env` file:

```bash
# For proxy usage
ANTHROPIC_BASE_URL=http://localhost:8080

# For direct API usage
# ANTHROPIC_API_KEY=your-key-here
```

## 📈 Understanding the Data

### Key Metrics

- **Tokens**: Input/output tokens used
- **Cost**: USD cost per request
- **Cache**: Tokens saved via caching
- **Requests**: Number of API calls
- **Models**: Which Claude models used

### Reports Explained

1. **Daily Report**: Shows today's usage patterns
2. **Monthly Report**: Aggregates monthly statistics
3. **Session Report**: Groups by conversation session
4. **Blocks Report**: 5-hour billing windows
5. **Realtime Monitor**: Live usage tracking

## 💡 Best Practices

### 1. Regular Monitoring
```bash
# Check daily
npx ccusage daily

# Weekly analysis
npx ccusage monthly --since $(date -d "1 week ago" +%Y%m%d)

# Monthly review
npx ccusage monthly --breakdown
```

### 2. Cost Optimization
```bash
# Identify expensive sessions
npx ccusage session --breakdown | grep "HIGH"

# Find cache efficiency
npx ccusage monthly --breakdown | grep "Cache"
```

### 3. Project Tracking
```bash
# Filter by project name
npx ccusage daily --project AERO_Agent

# Compare periods
npx ccusage monthly --since 20260101 > usage-week1.json
npx ccusage monthly --since 20260108 > usage-week2.json
```

### 4. Automation
```bash
# Add to your workflow
echo "Daily usage check:" >> usage-log.txt
npx ccusage daily --compact >> usage-log.txt

# Weekly summary script
./scripts/usage-monitor.sh monthly --since $(date -d "1 week ago" +%Y%m%d) > weekly-report.txt
```

## 🔧 Troubleshooting

### Common Issues

1. **No data showing**
   ```bash
   # Check if Claude Code has run
   ls ~/.claude/
   npx ccusage --help
   ```

2. **Permission denied**
   ```bash
   # Fix script permissions
   chmod +x scripts/*.sh
   ```

3. **Proxy not responding**
   ```bash
   # Check if proxy is running
   ps aux | grep better-ccflare
   curl http://localhost:8080/health
   ```

4. **Configuration not loading**
   ```bash
   # Specify config explicitly
   claude-monitor --config .config/usage-monitors/config.toml
   ```

### Getting Help

```bash
# CC Usage help
npx ccusage --help

# Claude Monitor help
claude-monitor --help

# Check proxy status
curl http://localhost:8080/health
```

## 📚 Additional Resources

- [CC Usage GitHub](https://github.com/ryoppippi/ccusage)
- [better-ccflare GitHub](https://github.com/tombii/better-ccflare)
- [Claude Code Usage Monitor](https://github.com/Maciek-roboblog/Claude-Code-Usage-Monitor)
- [awesome-claude-code](https://github.com/hesreallyhim/awesome-claude-code)

## 🎨 Customization

### Create Your Own Commands

Add to `.claude/commands/`:

```bash
# .claude/commands/usage-weekly.md
# Weekly usage analysis for AERO_Agent

./scripts/usage-monitor.sh monthly --since $(date -d "1 week ago" +%Y%m%d)
```

### Dashboard Customization

Edit `.config/usage-monitors/config.toml`:

```toml
[display]
show_progress_bar = true
show_predictions = true
refresh_rate = 1  # Faster updates
theme = "dark"
```

---

**💡 Pro Tip**: Start with `npx ccusage daily` to get a quick overview, then explore the more advanced features as needed!
