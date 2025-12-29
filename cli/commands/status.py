"""
Status command - Show Hantu Quant service status.

Usage:
    hantu status [SERVICE]
"""

import os
import click

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

SERVICES = ['scheduler', 'api']
SERVICE_NAMES = {
    'scheduler': 'Integrated Scheduler',
    'api': 'API Server',
}


@click.command()
@click.argument('service', type=click.Choice(['scheduler', 'api', 'all']), default='all', required=False)
@click.option('--json', 'as_json', is_flag=True, help='Output as JSON.')
@click.pass_context
def status(ctx: click.Context, service: str, as_json: bool) -> None:
    """Show status of Hantu Quant services.

    \b
    Examples:
        hantu status             Show all service statuses
        hantu status scheduler   Show only scheduler status
        hantu status --json      Output as JSON
    """
    from core.process.registry import ProcessRegistry

    registry = ProcessRegistry()

    services_to_check = SERVICES if service == 'all' else [service]

    statuses = {}
    for svc_name in services_to_check:
        status_info = registry.get_status(svc_name)
        statuses[svc_name] = {
            'name': SERVICE_NAMES.get(svc_name, svc_name),
            'running': status_info.is_running,
            'pid': status_info.pid,
            'uptime': status_info.uptime_str,
            'memory_mb': status_info.memory_mb,
        }

    if as_json:
        import json
        click.echo(json.dumps(statuses, indent=2))
    else:
        _print_status_table(statuses)


def _print_status_table(statuses: dict) -> None:
    """Print status as a formatted table."""
    click.echo()
    click.echo("Service Status")
    click.echo("=" * 60)

    for svc_name, info in statuses.items():
        status_icon = click.style("●", fg='green') if info['running'] else click.style("○", fg='red')
        status_text = "running" if info['running'] else "stopped"

        click.echo(f"{status_icon} {info['name']:<25} {status_text:<10}", nl=False)

        if info['running']:
            click.echo(f" PID: {info['pid']:<8}", nl=False)
            if info['uptime']:
                click.echo(f" Uptime: {info['uptime']:<12}", nl=False)
            if info['memory_mb']:
                click.echo(f" Memory: {info['memory_mb']:.1f}MB", nl=False)

        click.echo()

    click.echo("=" * 60)

    # Summary
    running = sum(1 for info in statuses.values() if info['running'])
    total = len(statuses)
    click.echo(f"Total: {running}/{total} services running")
    click.echo()
