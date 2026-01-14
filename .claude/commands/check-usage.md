# Check Claude Code Usage

Analyze your Claude Code usage patterns, costs, and token consumption for the AERO_Agent project.

## Usage

### Daily Usage
```bash
npx ccusage daily
npx ccusage daily --breakdown
npx ccusage daily --project AERO_Agent
```

### Monthly Summary
```bash
npx ccusage monthly
npx ccusage monthly --breakdown
npx ccusage monthly --since 20260101
```

### Session Analysis
```bash
npx ccusage session
npx ccusage session --breakdown --since 20260101
```

### Cost Breakdown
```bash
npx ccusage monthly --breakdown --json > usage-report.json
```

### Custom Date Range
```bash
npx ccusage daily --since 20260101 --until 20260113 --timezone Asia/Shanghai
```

## Claude Code Usage Monitor (Real-time)

If installed with `uv tool install claude-monitor`:

```bash
# Real-time monitoring
claude-monitor --plan pro --view realtime --theme dark

# Daily view
claude-monitor --view daily --theme dark

# Monthly statistics
claude-monitor --view monthly --theme dark
```

## Tips

- Use `--json` flag for data export and analysis
- Combine with `| less` for large reports
- Use `--compact` for terminal-friendly output
- Check `--help` for all options
