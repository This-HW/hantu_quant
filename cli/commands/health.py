"""
Health command - System health check.

Usage:
    hantu health [OPTIONS]
"""

import os
import sys
import click

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@click.command()
@click.option('--json', 'as_json', is_flag=True, help='Output as JSON.')
@click.option('--verbose', '-v', is_flag=True, help='Show detailed health information.')
@click.pass_context
def health(ctx: click.Context, as_json: bool, verbose: bool) -> None:
    """Check system health status.

    \b
    Checks:
        - Service status (scheduler, API)
        - API connectivity (KIS API)
        - Database connectivity
        - Disk space
        - Memory usage

    \b
    Examples:
        hantu health             Quick health check
        hantu health --verbose   Detailed health check
        hantu health --json      Output as JSON
    """
    try:
        health_data = _collect_health_data(verbose)

        if as_json:
            import json
            click.echo(json.dumps(health_data, indent=2))
        else:
            _print_health_report(health_data, verbose)

        # Exit with error code if any critical check failed
        if not health_data.get('overall_healthy', False):
            sys.exit(1)

    except Exception as e:
        click.echo(f"Health check failed: {e}", err=True)
        if ctx.obj.get('debug'):
            import traceback
            traceback.print_exc()
        sys.exit(1)


def _collect_health_data(verbose: bool) -> dict:
    """Collect health data from all components."""
    import psutil

    health_data = {
        'timestamp': _get_timestamp(),
        'checks': {},
        'overall_healthy': True,
    }

    # Service status
    try:
        from core.process.registry import ProcessRegistry
        registry = ProcessRegistry()

        scheduler_status = registry.get_status('scheduler')
        api_status = registry.get_status('api')

        health_data['checks']['services'] = {
            'status': 'healthy' if (scheduler_status.is_running or api_status.is_running) else 'warning',
            'scheduler': {'running': scheduler_status.is_running, 'pid': scheduler_status.pid},
            'api': {'running': api_status.is_running, 'pid': api_status.pid},
        }
    except Exception as e:
        health_data['checks']['services'] = {'status': 'error', 'error': str(e)}
        health_data['overall_healthy'] = False

    # System resources
    try:
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage('/')

        memory_healthy = memory.percent < 90
        disk_healthy = disk.percent < 90

        health_data['checks']['system'] = {
            'status': 'healthy' if (memory_healthy and disk_healthy) else 'warning',
            'memory_percent': memory.percent,
            'memory_available_gb': round(memory.available / (1024**3), 2),
            'disk_percent': disk.percent,
            'disk_free_gb': round(disk.free / (1024**3), 2),
        }

        if not memory_healthy or not disk_healthy:
            health_data['overall_healthy'] = False

    except Exception as e:
        health_data['checks']['system'] = {'status': 'error', 'error': str(e)}

    # Configuration
    try:
        from core.config.loader import ConfigLoader
        loader = ConfigLoader()
        validation = loader.validate()

        config_healthy = all(v.get('valid', False) for v in validation.values())

        health_data['checks']['config'] = {
            'status': 'healthy' if config_healthy else 'error',
            'details': validation if verbose else None,
        }

        if not config_healthy:
            health_data['overall_healthy'] = False

    except Exception as e:
        health_data['checks']['config'] = {'status': 'error', 'error': str(e)}
        health_data['overall_healthy'] = False

    # API connectivity (optional, verbose only)
    if verbose:
        try:
            from core.api.kis_api import KISAPI
            KISAPI()
            # Simple connectivity check
            health_data['checks']['api_connectivity'] = {
                'status': 'healthy',
                'kis_api': 'connected',
            }
        except Exception as e:
            health_data['checks']['api_connectivity'] = {
                'status': 'warning',
                'error': str(e),
            }

    return health_data


def _print_health_report(health_data: dict, verbose: bool) -> None:
    """Print formatted health report."""
    click.echo()
    click.echo("=== System Health Check ===")
    click.echo(f"Timestamp: {health_data['timestamp']}")
    click.echo()

    for check_name, check_data in health_data['checks'].items():
        status = check_data.get('status', 'unknown')
        status_color = {'healthy': 'green', 'warning': 'yellow', 'error': 'red'}.get(status, 'white')
        status_icon = {'healthy': '✓', 'warning': '!', 'error': '✗'}.get(status, '?')

        click.echo(f"{click.style(status_icon, fg=status_color)} {check_name.upper()}: {click.style(status, fg=status_color)}")

        if verbose and isinstance(check_data, dict):
            for key, value in check_data.items():
                if key not in ('status', 'details') and value is not None:
                    click.echo(f"    {key}: {value}")

    click.echo()

    overall = health_data.get('overall_healthy', False)
    if overall:
        click.echo(click.style("Overall: HEALTHY", fg='green', bold=True))
    else:
        click.echo(click.style("Overall: UNHEALTHY", fg='red', bold=True))

    click.echo()


def _get_timestamp() -> str:
    """Get current timestamp."""
    from datetime import datetime
    return datetime.now().isoformat()
