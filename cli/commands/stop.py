"""
Stop command - Stop Hantu Quant services.

Usage:
    hantu stop [SERVICE]

Services:
    scheduler   Integrated scheduler
    api         API server
    all         All services
"""

import os
import signal
import time
import click

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

SERVICES = ['scheduler', 'api']
SERVICE_NAMES = {
    'scheduler': 'Integrated Scheduler',
    'api': 'API Server',
}


@click.command()
@click.argument('service', type=click.Choice(['scheduler', 'api', 'all']), default='all')
@click.option('--force', '-f', is_flag=True, help='Force kill (SIGKILL) instead of graceful shutdown.')
@click.option('--timeout', '-t', type=int, default=30, help='Timeout in seconds for graceful shutdown.')
@click.pass_context
def stop(ctx: click.Context, service: str, force: bool, timeout: int) -> None:
    """Stop Hantu Quant services.

    \b
    Examples:
        hantu stop               Stop all services gracefully
        hantu stop scheduler     Stop only the scheduler
        hantu stop -f all        Force kill all services
    """
    from core.process.registry import ProcessRegistry

    registry = ProcessRegistry()

    services_to_stop = SERVICES if service == 'all' else [service]

    for svc_name in services_to_stop:
        svc_display = SERVICE_NAMES.get(svc_name, svc_name)
        click.echo(f"Stopping {svc_display}...")

        status = registry.get_status(svc_name)
        if not status.is_running:
            click.echo(f"  {svc_display} is not running")
            # Clean up stale PID file if exists
            registry.unregister(svc_name)
            continue

        pid = status.pid
        try:
            if force:
                os.kill(pid, signal.SIGKILL)
                click.echo(f"  {svc_display} force killed (PID: {pid})")
            else:
                # Graceful shutdown with SIGTERM
                os.kill(pid, signal.SIGTERM)

                # Wait for process to terminate
                if _wait_for_termination(pid, timeout):
                    click.echo(f"  {svc_display} stopped gracefully (PID: {pid})")
                else:
                    click.echo(f"  {svc_display} did not stop within {timeout}s, force killing...")
                    os.kill(pid, signal.SIGKILL)
                    click.echo(f"  {svc_display} force killed (PID: {pid})")

            registry.unregister(svc_name)

        except ProcessLookupError:
            click.echo(f"  {svc_display} process not found (stale PID file)")
            registry.unregister(svc_name)
        except PermissionError:
            click.echo(f"  Permission denied to stop {svc_display} (PID: {pid})", err=True)
        except Exception as e:
            click.echo(f"  Failed to stop {svc_display}: {e}", err=True)
            if ctx.obj.get('debug'):
                import traceback
                traceback.print_exc()


def _wait_for_termination(pid: int, timeout: int) -> bool:
    """Wait for process to terminate. Returns True if terminated, False if timeout."""
    start_time = time.time()
    while time.time() - start_time < timeout:
        try:
            os.kill(pid, 0)  # Check if process exists
            time.sleep(0.5)
        except ProcessLookupError:
            return True
    return False
