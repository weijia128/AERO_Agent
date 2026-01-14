# AERO_Agent Scripts Directory

This directory contains utility scripts for monitoring and managing Claude Code and Codex usage.

## 📋 Script Index

### 🔧 Installation & Setup

#### `install-tools.sh`
**Purpose:** Install all required monitoring tools
**Usage:**
```bash
./scripts/install-tools.sh
```
**What it does:**
- Checks prerequisites (Node.js, npm, Docker, UV)
- Installs better-ccflare globally
- Installs claude-monitor via UV
- Verifies installations

#### `setup-ccflare-env.sh`
**Purpose:** Configure environment for better-ccflare
**Usage:**
```bash
./scripts/setup-ccflare-env.sh
```
**What it does:**
- Checks if better-ccflare is running
- Sets up environment variables
- Adds configuration to shell profile

### 🚀 Startup & Proxy

#### `start-proxy.sh`
**Purpose:** Start better-ccflare proxy with Docker
**Usage:**
```bash
./scripts/start-proxy.sh
```
**What it does:**
- Checks Docker is running
- Starts better-ccflare container
- Configures environment
- Shows access instructions

#### `start-ccflare-docker.sh`
**Purpose:** Start better-ccflare using Docker directly
**Usage:**
```bash
./scripts/start-ccflare-docker.sh
```
**What it does:**
- Alternative to start-proxy.sh
- Manual Docker container management

### 📊 Monitoring & Analysis

#### `usage-monitor.sh`
**Purpose:** Comprehensive Claude Code usage monitoring
**Usage:**
```bash
./scripts/usage-monitor.sh [daily|monthly|session|realtime|cost|export]
```
**Options:**
- `daily` - Daily usage report
- `monthly` - Monthly usage report
- `session` - Session analysis
- `realtime` - Real-time monitoring
- `cost` - Cost breakdown export
- `export` - Full data export

**What it does:**
- Runs ccusage with various options
- Generates usage reports
- Supports JSON export

#### `analyze-codex-usage.sh`
**Purpose:** Analyze Codex CLI usage from logs
**Usage:**
```bash
./scripts/analyze-codex-usage.sh
```
**What it does:**
- Analyzes Codex log file
- Shows tool usage breakdown
- Displays working directory statistics
- Reports errors and sessions

#### `quick-check.sh`
**Purpose:** Quick health check of all monitoring tools
**Usage:**
```bash
./scripts/quick-check.sh
```
**What it does:**
- Checks better-ccflare status
- Verifies ccusage availability
- Checks claude-monitor installation
- Shows recent usage summary
- Displays system information

### 📈 Reports & Maintenance

#### `weekly-report.sh`
**Purpose:** Generate comprehensive weekly usage report
**Usage:**
```bash
./scripts/weekly-report.sh
```
**What it does:**
- Generates daily summaries
- Creates monthly overviews
- Analyzes sessions
- Produces markdown report
- Saves to `reports/` directory

#### `cleanup.sh`
**Purpose:** Cleanup and maintenance
**Usage:**
```bash
./scripts/cleanup.sh
```
**What it does:**
- Removes old reports (30+ days)
- Cleans temporary files
- Prunes Docker resources
- Analyzes log sizes
- Generates maintenance report

## 🎯 Quick Start Guide

### 1. First Time Setup
```bash
# Install all tools
./scripts/install-tools.sh

# Start better-ccflare
./scripts/start-proxy.sh

# Verify setup
./scripts/quick-check.sh
```

### 2. Daily Monitoring
```bash
# Quick status check
./scripts/quick-check.sh

# View daily usage
npx ccusage daily --breakdown

# Real-time monitoring
claude-monitor --plan pro --view realtime
```

### 3. Weekly Analysis
```bash
# Generate weekly report
./scripts/weekly-report.sh

# View report
cat reports/weekly-summary-$(date +%Y%m%d).md
```

### 4. Maintenance
```bash
# Cleanup old files
./scripts/cleanup.sh

# Check system health
./scripts/quick-check.sh
```

## 📁 Directory Structure

```
scripts/
├── README.md                    # This file
├── install-tools.sh            # Tool installer
├── setup-ccflare-env.sh       # Environment setup
├── start-proxy.sh             # Start proxy
├── start-ccflare-docker.sh    # Docker startup
├── usage-monitor.sh           # Usage monitoring
├── analyze-codex-usage.sh     # Codex analysis
├── quick-check.sh             # Health check
├── weekly-report.sh            # Weekly reports
└── cleanup.sh                 # Maintenance

reports/                       # Generated reports
├── weekly-summary-*.md        # Weekly summaries
├── claude-*.txt               # Claude usage reports
├── codex-analysis-*.txt      # Codex analysis
└── maintenance-*.md           # Maintenance reports
```

## 🔗 Integration with Other Tools

### With Claude Code
- Use `/check-usage` command in Claude Code
- Reference `.claude/commands/check-usage.md`

### With better-ccflare
- Web dashboard: http://localhost:8080
- API endpoint: http://localhost:8080/health

### With External Monitoring
- Export JSON reports for external analysis
- Integrate with cron for automated reports

## 🐛 Troubleshooting

### Tools not found
```bash
# Reinstall tools
./scripts/install-tools.sh

# Check PATH
echo $PATH | grep -E "(node|npm|uv)"
```

### Docker issues
```bash
# Check Docker status
docker ps

# Restart Docker Desktop
# Check container logs
docker logs better-ccflare
```

### Permission errors
```bash
# Make scripts executable
chmod +x scripts/*.sh

# Check file permissions
ls -la scripts/
```

## 📞 Support

For issues or questions:
1. Check the troubleshooting section
2. Run `./scripts/quick-check.sh`
3. Review logs in `reports/` directory
4. Check Docker container logs

## 🔄 Automation

### Cron Jobs
Add to crontab for automated monitoring:

```bash
# Daily health check at 9 AM
0 9 * * * /path/to/scripts/quick-check.sh

# Weekly report on Sundays at 10 AM
0 10 * * 0 /path/to/scripts/weekly-report.sh

# Monthly cleanup on 1st at 2 AM
0 2 1 * * /path/to/scripts/cleanup.sh
```

### Shell Aliases
Add to `~/.zshrc` or `~/.bashrc`:

```bash
# Usage monitoring
alias cc-usage='./scripts/usage-monitor.sh'
alias cc-check='./scripts/quick-check.sh'
alias cc-weekly='./scripts/weekly-report.sh'

# Quick commands
alias cc-daily='npx ccusage daily'
alias cc-monthly='npx ccusage monthly'
alias cc-monitor='claude-monitor --plan pro --view realtime'
```

## 📊 Best Practices

1. **Regular Monitoring**
   - Check daily: `./scripts/quick-check.sh`
   - Weekly reports: `./scripts/weekly-report.sh`
   - Monthly cleanup: `./scripts/cleanup.sh`

2. **Data Retention**
   - Keep daily reports for 7 days
   - Keep weekly reports for 30 days
   - Keep monthly summaries for 1 year

3. **Performance**
   - Monitor Docker disk usage
   - Archive old logs
   - Clean temporary files regularly

4. **Security**
   - Don't commit usage reports
   - Review Docker container security
   - Monitor API key usage

---

**Version:** 1.0
**Last Updated:** 2026-01-13
