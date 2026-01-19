#!/usr/bin/env python3
"""
Hantu Quant CLI - Unified Command Line Interface

Usage:
    hantu [OPTIONS] COMMAND [ARGS]...

Commands:
    start       Start services (scheduler, api, all)
    stop        Stop services
    status      Show service status
    trade       Trading operations
    screen      Stock screening (Phase 1)
    select      Daily selection (Phase 2)
    config      Configuration management
    health      System health check
    logs        View logs
"""

import sys
import os

# Ensure project root is in path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import click  # noqa: E402

from cli import __version__  # noqa: E402


class AliasedGroup(click.Group):
    """Custom Click group that supports command aliases."""

    def get_command(self, ctx: click.Context, cmd_name: str) -> click.Command | None:
        """Get command with alias support."""
        # Direct match
        rv = click.Group.get_command(self, ctx, cmd_name)
        if rv is not None:
            return rv

        # Alias mapping
        aliases = {
            'run': 'start',
            'st': 'status',
            'ps': 'status',
        }

        if cmd_name in aliases:
            return click.Group.get_command(self, ctx, aliases[cmd_name])

        return None


@click.group(cls=AliasedGroup, invoke_without_command=True)
@click.option('--version', '-v', is_flag=True, help='Show version and exit.')
@click.option('--debug', is_flag=True, help='Enable debug mode.')
@click.pass_context
def cli(ctx: click.Context, version: bool, debug: bool) -> None:
    """Hantu Quant - AI-based Stock Trading System CLI

    A unified command-line interface for managing the Hantu Quant trading system.

    \b
    Quick Start:
        hantu start all         Start all services
        hantu status            Check service status
        hantu stop all          Stop all services

    \b
    Trading:
        hantu trade balance     Check account balance
        hantu screen            Run stock screening
        hantu select            Run daily selection
    """
    ctx.ensure_object(dict)
    ctx.obj['debug'] = debug

    if version:
        click.echo(f"hantu-quant version {__version__}")
        ctx.exit(0)

    if ctx.invoked_subcommand is None:
        click.echo(ctx.get_help())


# Import and register commands
from cli.commands.start import start  # noqa: E402
from cli.commands.stop import stop  # noqa: E402
from cli.commands.status import status  # noqa: E402
from cli.commands.trade import trade  # noqa: E402
from cli.commands.screen import screen  # noqa: E402
from cli.commands.select import select  # noqa: E402
from cli.commands.config import config  # noqa: E402
from cli.commands.health import health  # noqa: E402
from cli.commands.logs import logs  # noqa: E402

cli.add_command(start)
cli.add_command(stop)
cli.add_command(status)
cli.add_command(trade)
cli.add_command(screen)
cli.add_command(select)
cli.add_command(config)
cli.add_command(health)
cli.add_command(logs)


def main() -> None:
    """Main entry point for the CLI."""
    try:
        cli(obj={})
    except KeyboardInterrupt:
        click.echo("\nOperation cancelled.")
        sys.exit(130)
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
