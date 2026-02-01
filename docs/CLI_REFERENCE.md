# Hantu CLI Reference

**Version**: 1.0.0

## Overview

`hantu` is the unified command-line interface for managing the Hantu Quant trading system. It consolidates all service management, trading operations, and system utilities into a single entry point.

## Installation

```bash
# Install in development mode
pip install -e .

# Or install from requirements
pip install -r requirements.txt
```

After installation, the `hantu` command will be available globally.

## Quick Start

```bash
# Start all services
hantu start all

# Check status
hantu status

# Check account balance
hantu trade balance

# Run stock screening
hantu screen

# Stop all services
hantu stop all
```

## Commands

### Service Management

#### `hantu start`

Start Hantu Quant services.

```bash
hantu start [SERVICE] [OPTIONS]

Services:
  scheduler    Integrated scheduler (Phase 1 + Phase 2 + Trading)
  api          API server
  all          All services (default)

Options:
  -f, --foreground    Run in foreground (do not daemonize)
  -w, --workers INT   Number of parallel workers (scheduler only)

Examples:
  hantu start              # Start all services
  hantu start scheduler    # Start only scheduler
  hantu start -f scheduler # Run scheduler in foreground
  hantu start -w 8 all     # Start with 8 workers
```

#### `hantu stop`

Stop Hantu Quant services.

```bash
hantu stop [SERVICE] [OPTIONS]

Services:
  scheduler    Integrated scheduler
  api          API server
  all          All services (default)

Options:
  -f, --force         Force kill (SIGKILL) instead of graceful shutdown
  -t, --timeout INT   Timeout in seconds for graceful shutdown (default: 30)

Examples:
  hantu stop               # Stop all services gracefully
  hantu stop scheduler     # Stop only scheduler
  hantu stop -f all        # Force kill all services
  hantu stop -t 60 all     # Wait up to 60s for graceful shutdown
```

#### `hantu status`

Show service status.

```bash
hantu status [SERVICE] [OPTIONS]

Services:
  scheduler    Integrated scheduler
  api          API server
  all          All services (default)

Options:
  --json    Output as JSON

Examples:
  hantu status             # Show all service statuses
  hantu status scheduler   # Show only scheduler status
  hantu status --json      # Output as JSON
```

### Trading Operations

#### `hantu trade`

Trading operations subcommands.

```bash
hantu trade [SUBCOMMAND]

Subcommands:
  balance     Check account balance
  positions   Show current positions
  find        Find candidate stocks

Examples:
  hantu trade balance      # Check account balance
  hantu trade positions    # Show current positions
  hantu trade find         # Find candidate stocks
  hantu trade find -n 20   # Show top 20 candidates
```

### Stock Analysis

#### `hantu screen`

Run stock screening (Phase 1).

```bash
hantu screen [OPTIONS]

Options:
  -p, --parallel INT   Number of parallel workers (default: 4)
  --list               Show current watchlist
  --add CODE           Add stock to watchlist
  --remove CODE        Remove stock from watchlist

Examples:
  hantu screen              # Run screening
  hantu screen -p 8         # Run with 8 workers
  hantu screen --list       # Show watchlist
  hantu screen --add 005930 # Add Samsung to watchlist
```

#### `hantu select`

Run daily selection (Phase 2).

```bash
hantu select [OPTIONS]

Options:
  -p, --parallel INT   Number of parallel workers (default: 4)
  -a, --analyze        Run analysis mode (detailed output)
  -s, --show           Show current daily selection
  -c, --criteria       Show selection criteria

Examples:
  hantu select              # Run daily selection
  hantu select -p 8         # Run with 8 workers
  hantu select --analyze    # Run detailed analysis
  hantu select --show       # Show today's selections
  hantu select --criteria   # Show selection criteria
```

### Configuration

#### `hantu config`

Configuration management.

```bash
hantu config [SUBCOMMAND]

Subcommands:
  check    Validate configuration
  show     Show current configuration (masked)

Options for 'check':
  -v, --verbose    Show detailed validation results

Options for 'show':
  --unmask    Show unmasked values (dangerous!)

Examples:
  hantu config check           # Validate configuration
  hantu config check -v        # Verbose validation
  hantu config show            # Show config (masked)
  hantu config show --unmask   # Show config (unmasked)
```

### System Health

#### `hantu health`

Check system health status.

```bash
hantu health [OPTIONS]

Options:
  --json       Output as JSON
  -v, --verbose    Show detailed health information

Checks:
  - Service status (scheduler, API)
  - API connectivity (KIS API)
  - System resources (memory, disk)
  - Configuration validity

Examples:
  hantu health             # Quick health check
  hantu health --verbose   # Detailed health check
  hantu health --json      # Output as JSON
```

### Logs

#### `hantu logs`

View system logs from local files or database.

```bash
hantu logs [OPTIONS]

Options:
  -f, --follow         Follow log output (like tail -f)
  -n, --lines INT      Number of lines to show (default: 50)
  -s, --service NAME   Filter by service (all|scheduler|api|trading)
  -l, --level LEVEL    Filter by log level (DEBUG|INFO|WARNING|ERROR|CRITICAL)
  -d, --date DATE      Show logs for specific date (YYYYMMDD)
  --db                 Query from database (error logs only, permanent storage)
  --errors-only        Show only error logs (shortcut for -l ERROR)
  --json               Output as JSON format
  -t, --trace-id ID    Filter by trace ID (request tracking)

Log Locations:
  - Error logs (JSON):  logs/errors/error_YYYYMMDD.json
  - Info logs (Text):   logs/info/info_YYYYMMDD.log
  - DB error logs:      PostgreSQL error_logs table (permanent)
  - systemd journal:    journalctl -u hantu-scheduler (stderr only)

Retention Policy:
  - Local files:  3 days (auto-deleted)
  - DB logs:      Permanent (never deleted)

Examples:
  hantu logs                     # View recent logs (last 50 lines)
  hantu logs -f                  # Follow log output (real-time)
  hantu logs -n 100              # Show last 100 lines
  hantu logs -d 20260201         # Show logs for 2026-02-01
  hantu logs -l ERROR            # Show only error logs
  hantu logs --errors-only       # Same as above
  hantu logs --db                # Query from database (permanent storage)
  hantu logs --db -d 20260115    # DB logs for specific date
  hantu logs -t 1a2b3c4d         # Filter by trace ID
  hantu logs -s scheduler -f     # Follow scheduler logs only
  hantu logs --json              # Output as JSON

Direct File Access:
  # Error logs (JSON format, last 3 days)
  cat logs/errors/error_20260201.json
  jq '.[] | select(.level=="ERROR")' logs/errors/error_20260201.json

  # Info logs (Text format, last 3 days)
  tail -f logs/info/info_20260201.log
  grep "ERROR" logs/info/info_20260201.log

  # systemd journal (stderr only, error logs)
  journalctl -u hantu-scheduler -f
  journalctl -u hantu-api --since "1 hour ago"

Database Access:
  # Direct SQL query (permanent error logs)
  psql -U hantu hantu_quant -c "SELECT * FROM error_logs WHERE timestamp >= NOW() - INTERVAL '7 days' ORDER BY timestamp DESC LIMIT 50;"

  # With filters
  psql -U hantu hantu_quant -c "SELECT timestamp, level, logger, message FROM error_logs WHERE level = 'CRITICAL' ORDER BY timestamp DESC;"
```

**Note**:

- Local log files are auto-deleted after 3 days
- For long-term analysis, use `--db` option or query the database directly
- DB stores only ERROR and CRITICAL level logs permanently
- See `docs/planning/business-logic/logging-rules.md` for detailed logging policies

## Global Options

These options are available for all commands:

```bash
hantu [OPTIONS] COMMAND

Options:
  -v, --version    Show version and exit
  --debug          Enable debug mode
  --help           Show help message
```

## Exit Codes

| Code | Meaning              |
| ---- | -------------------- |
| 0    | Success              |
| 1    | General error        |
| 2    | Invalid arguments    |
| 130  | Interrupted (Ctrl+C) |

## Environment Variables

The CLI respects the following environment variables:

| Variable         | Description                   | Default    |
| ---------------- | ----------------------------- | ---------- |
| `APP_KEY`        | KIS API app key               | (required) |
| `APP_SECRET`     | KIS API app secret            | (required) |
| `ACCOUNT_NUMBER` | Trading account number        | (required) |
| `SERVER`         | Server mode (virtual/prod)    | virtual    |
| `LOG_LEVEL`      | Log level                     | INFO       |
| `API_SERVER_KEY` | API server authentication key | (optional) |

## Command Aliases

| Alias | Command  |
| ----- | -------- |
| `run` | `start`  |
| `st`  | `status` |
| `ps`  | `status` |

## See Also

- [User Guide](USER_GUIDE.md) - Detailed usage guide
- [API Reference](API_REFERENCE.md) - API documentation
- [Auto Trading Guide](AUTO_TRADING_GUIDE.md) - Auto trading setup
