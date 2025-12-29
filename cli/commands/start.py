"""
Start command - Start Hantu Quant services.

Usage:
    hantu start [SERVICE]

Services:
    scheduler   Integrated scheduler (Phase 1 + Phase 2 + Trading)
    api         API server
    all         All services
"""

import os
import sys
import subprocess
import click

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Service definitions
SERVICES = {
    'scheduler': {
        'name': 'Integrated Scheduler',
        'module': 'workflows.integrated_scheduler',
        'script': os.path.join(PROJECT_ROOT, 'workflows', 'integrated_scheduler.py'),
    },
    'api': {
        'name': 'API Server',
        'module': 'api-server.main',
        'script': os.path.join(PROJECT_ROOT, 'api-server', 'main.py'),
    },
}


@click.command()
@click.argument('service', type=click.Choice(['scheduler', 'api', 'all']), default='all')
@click.option('--foreground', '-f', is_flag=True, help='Run in foreground (do not daemonize).')
@click.option('--workers', '-w', type=int, default=4, help='Number of parallel workers (scheduler only).')
@click.pass_context
def start(ctx: click.Context, service: str, foreground: bool, workers: int) -> None:
    """Start Hantu Quant services.

    \b
    Examples:
        hantu start              Start all services
        hantu start scheduler    Start only the scheduler
        hantu start api          Start only the API server
        hantu start -f scheduler Run scheduler in foreground
    """
    # Import here to avoid circular imports and speed up CLI help
    from core.process.registry import ProcessRegistry

    registry = ProcessRegistry()

    services_to_start = list(SERVICES.keys()) if service == 'all' else [service]

    for svc_name in services_to_start:
        svc_info = SERVICES[svc_name]
        click.echo(f"Starting {svc_info['name']}...")

        # Check if already running
        status = registry.get_status(svc_name)
        if status.is_running:
            click.echo(f"  {svc_info['name']} is already running (PID: {status.pid})")
            continue

        try:
            if foreground and len(services_to_start) == 1:
                # Run in foreground
                _run_foreground(svc_name, svc_info, workers)
            else:
                # Run as background process
                pid = _run_background(svc_name, svc_info, workers)
                registry.register(svc_name, pid)
                click.echo(f"  {svc_info['name']} started (PID: {pid})")

        except Exception as e:
            click.echo(f"  Failed to start {svc_info['name']}: {e}", err=True)
            if ctx.obj.get('debug'):
                import traceback
                traceback.print_exc()


def _run_foreground(svc_name: str, svc_info: dict, workers: int) -> None:
    """Run service in foreground."""
    script = svc_info['script']
    cmd = [sys.executable, script]

    if svc_name == 'scheduler':
        cmd.extend(['--workers', str(workers)])

    os.execv(sys.executable, cmd)


def _run_background(svc_name: str, svc_info: dict, workers: int) -> int:
    """Run service as background process and return PID."""
    script = svc_info['script']
    cmd = [sys.executable, script]

    if svc_name == 'scheduler':
        cmd.extend(['--workers', str(workers)])

    # Start as detached process
    process = subprocess.Popen(
        cmd,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        stdin=subprocess.DEVNULL,
        start_new_session=True,
        cwd=PROJECT_ROOT,
    )

    return process.pid
