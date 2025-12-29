"""
Logs command - View system logs.

Usage:
    hantu logs [OPTIONS]
"""

import os
import sys
import glob
import click

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
LOG_DIR = os.path.join(PROJECT_ROOT, 'logs')


@click.command()
@click.option('--follow', '-f', is_flag=True, help='Follow log output (like tail -f).')
@click.option('--lines', '-n', type=int, default=50, help='Number of lines to show.')
@click.option('--service', '-s', type=click.Choice(['all', 'scheduler', 'api', 'trading']), default='all',
              help='Filter by service.')
@click.option('--level', '-l', type=click.Choice(['DEBUG', 'INFO', 'WARNING', 'ERROR']),
              help='Filter by log level.')
@click.option('--date', '-d', type=str, help='Show logs for specific date (YYYYMMDD).')
@click.pass_context
def logs(ctx: click.Context, follow: bool, lines: int, service: str, level: str, date: str) -> None:
    """View system logs.

    \b
    Examples:
        hantu logs                View recent logs
        hantu logs -f             Follow log output
        hantu logs -n 100         Show last 100 lines
        hantu logs -d 20241229    Show logs for specific date
        hantu logs -l ERROR       Show only error logs
    """
    try:
        # Find log file
        log_file = _find_log_file(date)

        if not log_file:
            click.echo("No log files found.", err=True)
            sys.exit(1)

        click.echo(f"Log file: {log_file}")
        click.echo("-" * 60)

        if follow:
            _follow_log(log_file, level)
        else:
            _show_log(log_file, lines, level)

    except KeyboardInterrupt:
        click.echo("\nStopped.")
    except Exception as e:
        click.echo(f"Failed to read logs: {e}", err=True)
        if ctx.obj.get('debug'):
            import traceback
            traceback.print_exc()
        sys.exit(1)


def _find_log_file(date: str | None) -> str | None:
    """Find the appropriate log file."""
    if not os.path.exists(LOG_DIR):
        return None

    if date:
        # Look for specific date
        pattern = os.path.join(LOG_DIR, f"{date}*.log")
        files = glob.glob(pattern)
        if files:
            return files[0]

        # Try alternative patterns
        pattern = os.path.join(LOG_DIR, f"*{date}*.log")
        files = glob.glob(pattern)
        if files:
            return files[0]

        return None

    # Find most recent log file
    pattern = os.path.join(LOG_DIR, "*.log")
    files = glob.glob(pattern)

    if not files:
        # Try trading.log as fallback
        trading_log = os.path.join(PROJECT_ROOT, 'trading.log')
        if os.path.exists(trading_log):
            return trading_log
        return None

    # Return most recently modified
    return max(files, key=os.path.getmtime)


def _show_log(log_file: str, lines: int, level: str | None) -> None:
    """Show log file contents."""
    with open(log_file, 'r', encoding='utf-8', errors='replace') as f:
        all_lines = f.readlines()

    # Filter by level if specified
    if level:
        filtered = [line for line in all_lines if level in line]
    else:
        filtered = all_lines

    # Show last N lines
    for line in filtered[-lines:]:
        _print_log_line(line.rstrip())


def _follow_log(log_file: str, level: str | None) -> None:
    """Follow log file output."""
    import time

    with open(log_file, 'r', encoding='utf-8', errors='replace') as f:
        # Go to end of file
        f.seek(0, 2)

        click.echo("Following log output (Ctrl+C to stop)...")
        click.echo()

        while True:
            line = f.readline()
            if line:
                if level is None or level in line:
                    _print_log_line(line.rstrip())
            else:
                time.sleep(0.1)


def _print_log_line(line: str) -> None:
    """Print a log line with color coding."""
    if 'ERROR' in line or 'CRITICAL' in line:
        click.echo(click.style(line, fg='red'))
    elif 'WARNING' in line:
        click.echo(click.style(line, fg='yellow'))
    elif 'DEBUG' in line:
        click.echo(click.style(line, fg='cyan'))
    else:
        click.echo(line)
